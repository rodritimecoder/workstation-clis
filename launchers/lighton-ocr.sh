#!/usr/bin/env bash
# lighton-ocr — LightOnOCR-3-0.8B Document & Video OCR server on port 8085.
#
# LightOnOCR-3-0.8B is a compact vision OCR model with two supported prompts:
#   ""          transcription only (flat page text as Markdown)
#   "grounding" every block as ![label](x1,y1,x2,y2) in 0-1000 page
#               coordinates, plus image descriptions and chart data tables
#
# The prompt is NOT a server option: llama-server applies the model's chat
# template and the client sends the prompt text with each request. This script
# names the machine default ("grounding") so every client agrees on it — the
# `ocr` skill reads OCR_LIGHTON_PROMPT from the environment, and its own
# default is the same value. Override per session with LIGHTON_PROMPT="".
#
# Stock upstream llama.cpp with Vulkan backend.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/prithivMLmods/LightOnOCR-3-0.8B-GGUF"

PORT="${PORT:-8085}"
CTX="${CTX:-8192}"
LIGHTON_PROMPT="${LIGHTON_PROMPT:-grounding}"
export OCR_LIGHTON_PROMPT="$LIGHTON_PROMPT"

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
echo "prompt: ${LIGHTON_PROMPT:-<empty: transcription>}  (client-side; LIGHTON_PROMPT overrides)"
echo "mode: Document / Slide / Video Text OCR, layout blocks + figure boxes"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  -np 1 \
  --reasoning off
