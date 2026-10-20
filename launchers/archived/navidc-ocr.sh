#!/usr/bin/env bash
# navidc-ocr — NaviDC-OCR document/VLM server on port 8082.
#
# Uses the patched upstream llama.cpp build: NaviDC-OCR sets head_dim=128 while
# hidden_size/num_heads=64, so stock qwen2vl hardcodes the wrong attn_q and
# attn_output shapes and the loader aborts. The patch is backward-compatible
# with stock Qwen2.5-VL GGUFs, so this same binary serves other vision models.
#
# The server build has no audio_decode frontend module, but images need none:
# the WebUI uploads them as base64 PNG/JPEG.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/nandraj/NaviDC-OCR-GGUF"

PORT="${PORT:-8082}"
MMPROJ="${MMPROJ:-$MODELS/NaviDC-OCR-mmproj-q8_0.gguf}"
CTX="${CTX:-16384}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

# Pick the first NaviDC OCR model present (q8_0 preferred).
MODEL=""
for cand in "$MODELS"/NaviDC-OCR-Q8_0.gguf "$MODELS"/NaviDC-OCR-Q4_K_M.gguf; do
  [ -f "$cand" ] && { MODEL="$cand"; break; }
done
[ -n "$MODEL" ] || { echo "no NaviDC-OCR model found in $MODELS"; exit 1; }
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=8084"
  exit 0
fi

echo "NaviDC-OCR on http://127.0.0.1:${PORT}  (ctx ${CTX})"
echo "model: $(basename "$MODEL")"
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
  --no-warmup \
  "$@"