#!/usr/bin/env bash
# bge-small.sh — BGE-small-en-v1.5 (384d) Fast Text Embedding Server on :8087
set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODEL="$DRIVE/models/unsloth/bge-small-en-v1.5-GGUF/bge-small-en-v1.5-f16.gguf"
PORT="${PORT:-8087}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

if curl -fsS -m 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Port ${PORT} already active."
  exit 0
fi

echo "🚀 Starting BGE-small-en-v1.5 (384d) on http://127.0.0.1:${PORT}..."
exec "$SERVER" \
  -m "$MODEL" \
  --embedding \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 0 \
  -c 512
