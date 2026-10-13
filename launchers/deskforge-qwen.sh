#!/usr/bin/env bash
# deskforge-qwen — DeskForge-Qwen3.5-4B Computer-Use & GUI Grounding server on port 8088.
#
# DeskForge-Qwen3.5-4B is a vision-language model fine-tuned for desktop GUI grounding
# and computer-use agent tasks, predicting normalized coordinates for pyautogui actions.
#
# Stock upstream llama.cpp with Vulkan backend.
# Requires:
#   --jinja: needed for the Qwen3.5 Jinja chat template
#   --image-min-tokens 1024: ensures Qwen-VL visual grounding accuracy

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/docling-project/DeskForge-Qwen3.5-4B"

PORT="${PORT:-8088}"
CTX="${CTX:-8192}"
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/DeskForge-Qwen3.5-4B.Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/DeskForge-Qwen3.5-4B.mmproj-bf16.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=8089"
  exit 0
fi

echo "DeskForge-Qwen3.5-4B on http://127.0.0.1:${PORT}  (ctx ${CTX})"
echo "model: $(basename "$MODEL") + $(basename "$MMPROJ")"
echo "mode: Computer Use / Desktop Grounding"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --jinja \
  --image-min-tokens "$IMAGE_MIN_TOKENS" \
  -ngl 99 \
  -c "$CTX" \
  -np 1
