#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="/run/media/rodri/AI"
SERVER="${HOME}/src/cafe-llama.cpp/build-vulkan/bin/llama-server"
TARGET="${AI_ROOT}/models/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
DRAFT="${AI_ROOT}/models/incoai/Qwen3.8-27B-DFlash2-GGUF/Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9931}"

for file in "$SERVER" "$TARGET" "$DRAFT"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Target: %s\nDraft: %s\nDevices: Vulkan0,Vulkan1 (layer split 50/50)\nContext: 262144 | target/draft KV: q4_0/q4_0 | DFlash n-max: 4\nListening: %s:%s\n' \
  "$TARGET" "$DRAFT" "$HOST" "$PORT"

exec "$SERVER" \
  -m "$TARGET" \
  -md "$DRAFT" \
  --spec-type draft-dflash \
  --spec-draft-n-max 4 \
  --spec-draft-device Vulkan0,Vulkan1 \
  --spec-draft-ngl 99 \
  -dev Vulkan0,Vulkan1 \
  -sm layer \
  -ts 50,50 \
  -mg 0 \
  -ngl 99 \
  -c 262144 \
  -np 1 \
  -b 2048 \
  -ub 512 \
  -ctk q4_0 \
  -ctv q4_0 \
  -ctkd q4_0 \
  -ctvd q4_0 \
  -fa on \
  --host "$HOST" \
  --port "$PORT"
