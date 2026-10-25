#!/usr/bin/env bash
# wevisone-vl.sh — WeVisOne-VL-4B visual grounding server on port 8088.
#
# Qwen3-VL-based unified perception: word-level OCR boxes, open-vocabulary
# detection, referring localization, pointing, counting. Emits structured
# <ref>…</ref><box>x1,y1,x2,y2</box> with 0-1000 normalized coordinates, and
# <box>none</box> when the queried target is absent.
#
# Not a chat model. It answers the prompt family the checkpoint was trained on
# (wevisone_vl/prompts.py); free-form "describe this image" collapses into
# boxes or invents detail. The grammar:
#
#   Locate all the instances that match the following description: a. b. c.
#   Locate the instances that match the following description: <phrase>.
#   point to: <label>
#   How many <label> in the image? Please count them with boxes.
#   How many <label> in the image?
#   detect all the word in the box format
#   Locate the following text in the image: <text>
#
# Grounding accuracy depends on image resolution: llama.cpp warns that Qwen-VL
# needs at least 1024 image tokens, so IMAGE_MIN_TOKENS defaults to 1024 here.
#
# Endpoints:
#   POST /v1/chat/completions  OpenAI-compatible, image as data URL
#   GET  /health               Health check
#
# Usage:
#   sh/wevisone-vl.sh                          # Q4_K_M + Q8 mmproj, port 8088
#   PORT=8091 sh/wevisone-vl.sh                # custom port
#   CTX=16384 sh/wevisone-vl.sh                # larger context
#   IMAGE_MIN_TOKENS=0 sh/wevisone-vl.sh       # let the server pick (faster, worse boxes)

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/mradermacher/WeVisOne-VL-4B-GGUF"

PORT="${PORT:-8088}"
HOST="${HOST:-127.0.0.1}"
CTX="${CTX:-8192}"
NGL="${NGL:-99}"
PARALLEL="${PARALLEL:-1}"
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/WeVisOne-VL-4B.Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/WeVisOne-VL-4B.mmproj-Q8_0.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=8091"
  exit 0
fi

echo "WeVisOne-VL-4B on http://${HOST}:${PORT}  (ctx ${CTX}, image-min-tokens ${IMAGE_MIN_TOKENS})"
echo "model: $(basename "$MODEL") + $(basename "$MMPROJ")"
echo "mode: visual grounding / OCR boxes / counting — not a chat model"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host "$HOST" \
  --port "$PORT" \
  -ngl "$NGL" \
  -c "$CTX" \
  -np "$PARALLEL" \
  --image-min-tokens "$IMAGE_MIN_TOKENS"
