#!/usr/bin/env bash
# minicpm-ocr-jev.sh — MiniCPM-OCR-Jev (2B reward model) on llama-server
#
# Slot: ocr-jev (:8090) — the OCR consistency gate. One fixed question, no
# generation: "is this OCR text faithful to this image?" The request carries
# state = the candidate OCR text and images = [original block, that candidate
# rendered back into an image], then one question: type "choice" with criteria
# {"0": null, "1": null} (1 = consistent) or type "noul" (P(consistent)).
# One forward pass; the class scores are pooled at the last token. Pair it with
# MiniCPM-OCR-1.0 (llama-mtmd-cli) as the candidate generator.
#
#   curl -s localhost:8090/v1/systemone -H 'Content-Type: application/json' -d '{
#     "state": "48520 Electronics & Circuits",
#     "images": ["data:image/png;base64,...", "data:image/png;base64,..."],
#     "questions": {"q": {"type": "noul"}}}'
#
# It is a decision model, but not a general one: the prompt is baked into the
# model and a request carrying "instructions" is rejected, so this slot cannot
# answer the jev-decision query types. :8083 remains the decision API.
#
# KV lives in system RAM (--no-kv-offload). Measured on 2x RX 9060 XT at ctx
# 40960: this saves ~5 GB VRAM (10.5 -> 5.3 GB at BATCH/UBATCH 8192) for +77 ms
# per block score (243 -> 316 ms); scores move by <3e-4. The GPU-KV path
# reserves ub*ctx attention scratch, which is what the offload actually removes.
# KV_RAM=0 keeps the cache on the GPU. BATCH/UBATCH 8192 is house style
# (one-pass headroom); Jev is causal and scores identically at 512 (2.7 GB, same
# speed), so on this model those are pure insurance. Do not add -ctk/-ctv q4_0:
# with KV already in RAM it saves nothing and moves scores ~2e-3.
#
# llama.cpp build: /run/media/rodri/AI/llama.cpp/build-vulkan (>= 7eed6b768, decision type openbmb-minicpm-ocr-jev)

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${OCRJEV_SERVER:-$DRIVE/llama.cpp/build-vulkan/bin/llama-server}"
MODEL_DIR="${OCRJEV_MODEL_DIR:-$DRIVE/models/openbmb/MiniCPM-OCR-Jev-gguf}"
MODEL="$MODEL_DIR/MiniCPM-OCR-Jev-Q6_K.gguf"
MMPROJ="$MODEL_DIR/mmproj-model-f16.gguf"

PORT="${PORT:-8090}"
HOST="${HOST:-127.0.0.1}"
CTX="${CTX:-40960}"
NGL="${NGL:-99}"
BATCH="${BATCH:-8192}"
UBATCH="${UBATCH:-8192}"
KV_RAM="${KV_RAM:-1}"
RESTART="${OCRJEV_RESTART:-0}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }
# The images are the input; without the projector this model is a doorstop.
[ -f "$MMPROJ" ] || { echo "missing mmproj (required, this model scores images): $MMPROJ"; exit 1; }

# The GGUF declares decision type "openbmb-minicpm-ocr-jev". An older build maps
# that string to UNKNOWN and then answers /v1/systemone with plausible but wrong
# scores instead of failing, so refuse to start on one.
if [ "${OCRJEV_SKIP_BUILD_CHECK:-0}" != "1" ] && \
   ! grep -qs "openbmb-minicpm-ocr-jev" "$SERVER" "$(dirname "$SERVER")"/libllama-common.so*; then
    echo "server does not know decision type openbmb-minicpm-ocr-jev"
    echo "  need llama.cpp >= 7eed6b768 (rebuild), or set OCRJEV_SKIP_BUILD_CHECK=1"
    exit 1
fi

KV_ARGS=()
[ "$KV_RAM" = "1" ] && KV_ARGS=(--no-kv-offload)

# The port is shared: stop whatever currently holds it.
if curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    if [ "$RESTART" = "1" ]; then
        echo "stopping the current holder of :$PORT"
        pkill -f "llama-server.*--port $PORT" 2>/dev/null
        sleep 3
    else
        echo "a server already holds :$PORT — set OCRJEV_RESTART=1 to replace it"
        exit 1
    fi
fi

echo "▶ minicpm-ocr-jev → :$PORT  (ngl=$NGL, ctx=$CTX, b=$BATCH ub=$UBATCH, kv=$([ "$KV_RAM" = "1" ] && echo ram || echo gpu))"

exec "$SERVER" \
    -m "$MODEL" \
    --mmproj "$MMPROJ" \
    --host "$HOST" \
    --port "$PORT" \
    -ngl "$NGL" \
    -c "$CTX" \
    -b "$BATCH" \
    -ub "$UBATCH" \
    "${KV_ARGS[@]}" \
    -np 1 \
    --no-webui
