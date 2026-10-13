#!/usr/bin/env bash
# imajev-4b — Imajev-4B decision-model server on port 8083.
#
# Imajev is a decision model: it returns a probability per option rather than
# generating text. Reading that out is client-side work — pull the option logits
# at the last position, divide by the calibration temperature, softmax. The
# temperature is NOT stored in the GGUF; it comes from calibration.json in the
# model dir (T = 1.3051569717552742).
#
# No custom llama.cpp fork is needed here: stock upstream loads both the model
# and its projector. (Contrast NaviDC-OCR, which does need the patch.)
#
# --image-min-tokens 1024: Qwen-VL warns that grounding degrades below this.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/mindchain/imajev-4b-GGUF"

PORT="${PORT:-8083}"
CTX="${CTX:-8192}"
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

# Prefer Q4_K_M (the quant the published calibration measurements used).
MODEL=""
for cand in "$MODELS"/imajev-4b-Q4_K_M.gguf "$MODELS"/imajev-4b-Q8_0.gguf "$MODELS"/imajev-4b-Q4_0.gguf; do
  [ -f "$cand" ] && { MODEL="$cand"; break; }
done
[ -n "$MODEL" ] || { echo "no Imajev-4B model found in $MODELS"; exit 1; }

MMPROJ="$MODELS/imajev-4b-mmproj-f16.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

CALIB="$MODELS/calibration.json"
if [ -f "$CALIB" ]; then
  T=$(python3 -c "import json;print(json.load(open('$CALIB'))['fit']['temperature'])" 2>/dev/null || echo "?")
  echo "calibration temperature: $T   (apply client-side to option logits)"
fi

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=8085"
  exit 0
fi

echo "Imajev-4B on http://127.0.0.1:${PORT}  (ctx ${CTX})"
echo "model: $(basename "$MODEL") + $(basename "$MMPROJ")"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  -b 2048 \
  -ub 512 \
  --image-min-tokens "$IMAGE_MIN_TOKENS" \
  --no-warmup \
  "$@"