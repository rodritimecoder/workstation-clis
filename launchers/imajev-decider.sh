#!/usr/bin/env bash
# imajev-decider.sh — Imajev-4B (Qwen3.5-4B + decision adapter) on llama-server
#
# Imajev-4B is a LoRA decision adapter merged into Qwen3.5-4B, with a vision
# projector. Two ways to serve it, both from this one script:
#
#   1. CHAT MODE (default) — ordinary OpenAI-compatible generation with images.
#      This is how the ImageJevBench *box* track measured it: "self-hosted vLLM
#      (adapter merged)", temperature 0, JSON box answer parsed by the harness.
#      The decision adapter has no native box head; the box comes from the base
#      model following a prompt. See docs/REPRODUCIBILITY.md in jevbench.
#
#   2. DECISION MODE (READOUT=1) — the letter/readout path: the answer code is
#      read from the option logits (A..Z -> token ids in decision_readout.json)
#      and calibrated with calibration.json (single temperature T=1.3052).
#
# VRAM note: both GPUs are usually saturated by the 35B on :8080, so the default
# is CPU inference (-ngl 0). Set NGL=99 to offload when the cards are free.
#
# llama.cpp build: /run/media/rodri/AI/llama.cpp/build-vulkan

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${IMAJEV_SERVER:-$DRIVE/llama.cpp/build-vulkan/bin/llama-server}"
MODEL_DIR="${IMAJEV_MODEL_DIR:-$DRIVE/models/mindchain/imajev-4b-GGUF}"
MODEL="$MODEL_DIR/imajev-4b-Q4_K_M.gguf"
MMPROJ="$MODEL_DIR/imajev-4b-mmproj-f16.gguf"

PORT="${PORT:-8089}"
HOST="${HOST:-127.0.0.1}"
CTX="${CTX:-16384}"
NGL="${NGL:-0}"
THREADS="${THREADS:-8}"
THREADS_BATCH="${THREADS_BATCH:-8}"
# An image expands into hundreds of tokens. The default physical batch (512)
# rejects the request with "input (N tokens) is too large to process", so the
# ubatch has to be as large as the context.
BATCH="${BATCH:-8192}"
UBATCH="${UBATCH:-8192}"
RESTART="${IMAJEV_RESTART:-0}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ_ARGS=()
[ -f "$MMPROJ" ] && MMPROJ_ARGS=(--mmproj "$MMPROJ")

# The decision slot is shared: stop whatever currently holds the port.
if curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    if [ "$RESTART" = "1" ]; then
        echo "stopping the current holder of :$PORT"
        pkill -f "llama-server.*--port $PORT" 2>/dev/null
        sleep 3
    else
        echo "a server already holds :$PORT — set IMAJEV_RESTART=1 to replace it"
        exit 1
    fi
fi

echo "▶ imajev-4B → :$PORT  (ngl=$NGL, ctx=$CTX, threads=$THREADS)"

exec "$SERVER" \
    -m "$MODEL" \
    "${MMPROJ_ARGS[@]}" \
    --host "$HOST" \
    --port "$PORT" \
    -ngl "$NGL" \
    -c "$CTX" \
    -b "$BATCH" \
    -ub "$UBATCH" \
    -t "$THREADS" \
    -tb "$THREADS_BATCH" \
    --jinja \
    --no-webui
