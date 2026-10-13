#!/usr/bin/env bash
# embeddinggemma-2 — Google EmbeddingGemma-2 on port 8087.
#
# Powered by Unsloth's Vulkan llama.cpp build supporting the new gemma-embedding2
# architecture. Supports both text embeddings and multimodal (text + vision + audio)
# via mmproj.
#
# Query example:
#   curl http://127.0.0.1:8087/v1/embeddings \
#     -H "Content-Type: application/json" \
#     -d '{"input": "Search text", "model": "embeddinggemma-2"}'

set -uo pipefail

DRIVE="/run/media/rodri/AI"
UNSLOTH_DIR="$DRIVE/unsloth_llamacpp-linux-x64-vulkan"
SERVER="$UNSLOTH_DIR/llama-server"
MODEL="$DRIVE/models/unsloth/embeddinggemma-2-GGUF/embeddinggemma-2-Q8_0.gguf"
MMPROJ="$DRIVE/models/unsloth/embeddinggemma-2-GGUF/mmproj-Q8_0.gguf"

PORT="${PORT:-8087}"
CTX="${CTX:-8192}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=..."
  exit 0
fi

# Ensure shared libraries from unsloth bundle are found
export LD_LIBRARY_PATH="$UNSLOTH_DIR:${LD_LIBRARY_PATH:-}"

echo "EmbeddingGemma-2 on http://127.0.0.1:${PORT} (ctx ${CTX})"
echo "Endpoints: /v1/embeddings"
if [ -f "$MMPROJ" ]; then
  echo "Multimodal mmproj: enabled ($MMPROJ)"
fi
echo "Ctrl-C to stop."
echo

EXTRA_ARGS=()
if [ -f "$MMPROJ" ]; then
  EXTRA_ARGS+=(--mmproj "$MMPROJ")
fi

exec "$SERVER" \
  -m "$MODEL" \
  "${EXTRA_ARGS[@]}" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  --embedding \
  --pooling mean \
  --no-webui
