#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="/run/media/rodri/AI"
SERVER="${LLAMA_SERVER_BIN:-$AI_ROOT/llama.cpp/build/bin/llama-server}"
MODEL="${LLAMA_MODEL:-$AI_ROOT/models/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF/Swift-1.5-Qwen3.8-27B-heretic-GSQ-RCO-IQ3_XXS-mtp.gguf}"
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"

for file in "$SERVER" "$MODEL"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Model: %s\nServing: http://%s:%s\nContext: 131072 | MTP draft max: 2 | KV cache: q4_0/q4_0\n' \
  "$MODEL" "$HOST" "$PORT"

exec "$SERVER" \
  -m "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  -c 131072 \
  -ngl 99 \
  -fa on \
  --jinja \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --spec-type draft-mtp \
  --spec-draft-n-max 2 \
  --chat-template-kwargs '{"reasoning_effort": "medium"}' \
  --reasoning on \
  --reasoning-budget 8192 \
  --temp 0.6 \
  --top-k 20 \
  --top-p 0.95 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --n-predict 32768 \
  "$@"
