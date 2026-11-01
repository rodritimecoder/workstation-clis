#!/usr/bin/env bash
# lighton-ocr — LightOnOCR-3-0.8B Document & Video OCR server on port 8085.
#
# LightOnOCR-3-0.8B is an ultra-fast vision OCR model (thinking variant: the
# transcription arrives in reasoning_content), used as the primary OCR engine
# in the video-miner pipeline.
#
# Stock upstream llama.cpp with Vulkan backend.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/prithivMLmods/LightOnOCR-3-0.8B-GGUF"

PORT="${PORT:-8085}"
CTX="${CTX:-8192}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/LightOnOCR-3-0.8B.Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/LightOnOCR-3-0.8B.mmproj-q8_0.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first (e.g. jev-style-2b), or use PORT=8089"
  exit 0
fi

echo "LightOnOCR-3-0.8B on http://127.0.0.1:${PORT}  (ctx ${CTX})"
echo "model: $(basename "$MODEL") + $(basename "$MMPROJ")"
echo "mode: Document / Slide / Video Text OCR"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  -np 1
