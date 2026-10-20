#!/usr/bin/env bash
# jev-style-2b — Jev-Style-Qwen3.5-2B-Decision on port 8085.
#
# Plain stock llama.cpp. Unlike the older jev-score binary path, this model
# serves as an ordinary GGUF and its calibration temperature is already baked
# into the weights — the readout is a plain renormalised softmax over the
# option-label logits, with no client-side temperature divide.
#
# jev-cli's --model jev points here; it starts this script on demand.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODEL="$DRIVE/models/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-GGUF/Jev-Style-Qwen3.5-2B-Decision-Q4_K_M.gguf"

PORT="${PORT:-8085}"
CTX="${CTX:-4096}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=8086"
  exit 0
fi

echo "Jev-Style-2B-Decision on http://127.0.0.1:${PORT}  (ctx ${CTX})"
echo "temperature is baked into the weights (no client-side divide)"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  --no-webui \
  --no-warmup \
  "$@"