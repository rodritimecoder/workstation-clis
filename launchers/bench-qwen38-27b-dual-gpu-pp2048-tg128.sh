#!/usr/bin/env bash
set -o pipefail

DRIVE="/run/media/rodri/AI"
BENCH_EXE="${DRIVE}/llama.cpp/build-vulkan/bin/llama-bench"
MODEL_PATH="${DRIVE}/models/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
REPORT_DIR="${HOME}/Desktop/llama-bench"
REPORT_FILE="${REPORT_DIR}/bench-qwen38-27b-dual-gpu-pp2048-tg128-$(date +%Y%m%d-%H%M%S).txt"

for file in "$BENCH_EXE" "$MODEL_PATH"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

mkdir -p "$REPORT_DIR"
printf 'Model: %s\n' "$MODEL_PATH"
printf 'Devices: Vulkan0 + Vulkan1 | split: layer 50/50 | pp: 2048 | tg: 128 | batch: 2048 | ubatch: 512 | KV: q4_0/q4_0\n'
printf 'Report: %s\n\n' "$REPORT_FILE"

"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  -dev Vulkan0/Vulkan1 \
  -sm layer \
  -ts 50/50 \
  -mg 0 \
  -ngl 99 \
  -p 2048 \
  -n 128 \
  -b 2048 \
  -ub 512 \
  -ctk q4_0 \
  -ctv q4_0 \
  -fa on \
  --progress \
  -r 1 \
  2>&1 | tee "$REPORT_FILE"
