#!/usr/bin/env bash
# onejev-4b.sh — OneJev1.5-4B Premier Decision & Vision Model Server
#
# Model: prithivMLmods/OneJev1.5-4B-GGUF (Q4_K_M)
# Vision: OneJev1.5-4B.mmproj-bf16.gguf
# Port: 8089 (fallback decision port; premier is vllm-d3-mini on 8083) or custom via PORT env var

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODELS="$DRIVE/models/prithivMLmods/OneJev1.5-4B-GGUF"

PORT="${PORT:-8089}"
CTX="${CTX:-8192}"
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/OneJev1.5-4B.Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/OneJev1.5-4B.mmproj-bf16.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "Stop it first (e.g. kill old Imajev PID), or use PORT=8088"
  exit 0
fi

echo "🚀 Starting OneJev1.5-4B on http://127.0.0.1:${PORT} (ctx ${CTX}, vision mmproj enabled)..."
echo "Model: $(basename "$MODEL") + $(basename "$MMPROJ")"
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
  --no-warmup
