#!/usr/bin/env bash
# Luffy Q4_K_M — Vulkan pp2048/tg128 benchmark
# Uses the upstream llama-bench with optimized dual RX 9060 XT settings.

DRIVE="/run/media/rodri/AI"
BENCH_EXE="${DRIVE}/llama.cpp/build/bin/llama-bench"
MODEL_PATH="${DRIVE}/models/LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-GGUF/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-Q4_K_M.gguf"
REPORT_DIR="${HOME}/Desktop/ROCmFPX"

mkdir -p "$REPORT_DIR"

for f in "$BENCH_EXE" "$MODEL_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

echo "Model: $MODEL_PATH"
echo "Benchmarking Qwen3.6-35B Q4_K_M on Vulkan (pp2048 / tg128)..."
echo

REPORT_FILE="${REPORT_DIR}/bench-luffy-q4km-$(date +%Y%m%d-%H%M%S).txt"

"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  -lm none \
  -p 2048 \
  -n 128 \
  -b 2048 \
  -ub 512 \
  -fa on \
  -sm layer \
  -ts 50/50 \
  -ngl 99 \
  -ctk q4_0 \
  -ctv q4_0 \
  -r 1 \
  2>&1 | tee "$REPORT_FILE"

echo
echo "Report saved to: $REPORT_FILE"
echo
read -r -p "Press [Enter] key to exit..."