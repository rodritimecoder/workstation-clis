#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="/run/media/rodri/AI"
SERVER="${LLAMA_SERVER_BIN:-${HOME}/build/llama.cpp-ggml/build-rocm/bin/llama-server}"
MODEL="${LLAMA_MODEL:-$AI_ROOT/models/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF/Swift-1.5-Qwen3.8-27B-heretic-GSQ-RCO-IQ3_XXS-mtp.gguf}"
TEMPLATE="${CHAT_TEMPLATE_FILE:-$AI_ROOT/models/froggeric/Qwen-Fixed-Chat-Templates/chat_template.jinja}"
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"
CTX="${LLAMA_CONTEXT:-131072}"
BATCH="${LLAMA_BATCH:-2048}"
UBATCH="${LLAMA_UBATCH:-512}"
DRAFT_N_MAX="${DRAFT_N_MAX:-4}"

export LD_LIBRARY_PATH="/opt/rocm/core-10.0/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

for pair in "CTX:$CTX" "BATCH:$BATCH" "UBATCH:$UBATCH" "DRAFT_N_MAX:$DRAFT_N_MAX"; do
  name="${pair%%:*}"
  value="${pair#*:}"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    printf '%s must be a positive integer\n' "$name" >&2
    exit 2
  fi
done
if ((UBATCH > BATCH)); then
  printf 'UBATCH (%s) cannot exceed BATCH (%s)\n' "$UBATCH" "$BATCH" >&2
  exit 2
fi

for file in "$SERVER" "$MODEL" "$TEMPLATE"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Model: %s\nBackend: ROCm 10 (HIP)\nDevices: ROCm0,ROCm1 (tensor split 50/50, fit off)\nContext: %s | MTP draft max: %s | KV cache: q4_0/q4_0 | batch/ubatch: %s/%s\nTemplate: %s | reasoning: on, medium\nServing: http://%s:%s\n' \
  "$MODEL" "$CTX" "$DRAFT_N_MAX" "$BATCH" "$UBATCH" "$TEMPLATE" "$HOST" "$PORT"

exec "$SERVER" \
  -m "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  -c "$CTX" \
  -dev ROCm0,ROCm1 \
  -sm tensor \
  -ts 50,50 \
  -mg 0 \
  -ngl all \
  --fit off \
  -np 1 \
  -b "$BATCH" \
  -ub "$UBATCH" \
  -fa on \
  --jinja \
  --chat-template-file "$TEMPLATE" \
  --reasoning-format deepseek \
  --reasoning on \
  --reasoning-effort medium \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --spec-type draft-mtp \
  --spec-draft-n-max "$DRAFT_N_MAX" \
  --temp 0.6 \
  --top-k 20 \
  --top-p 0.95 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --n-predict 32768 \
  "$@"
