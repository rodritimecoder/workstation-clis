#!/usr/bin/env bash
# jina-reranker — Jina-Reranker-v2-Base-Multilingual on port 8086.
#
# Dedicated cross-encoder reranker server providing standard OpenAI / Cohere
# compatible /v1/rerank endpoints for high-precision retrieval scoring.
#
# Query example:
#   curl http://127.0.0.1:8086/v1/rerank \
#     -H "Content-Type: application/json" \
#     -d '{"query": "my query", "documents": ["doc1", "doc2"]}'

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build/bin/llama-server"
MODEL="$DRIVE/models/gpustack/jina-reranker-v2-base-multilingual-GGUF/jina-reranker-v2-base-multilingual-Q8_0.gguf"

PORT="${PORT:-8086}"
CTX="${CTX:-4096}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "something is already answering on ${PORT}."
  echo "stop it first, or use PORT=..."
  exit 0
fi

echo "Jina-Reranker-v2 on http://127.0.0.1:${PORT} (ctx ${CTX})"
echo "Endpoints: /v1/rerank"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  --reranking \
  --no-webui
