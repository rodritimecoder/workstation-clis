#!/usr/bin/env bash
# Gemma 4 26B-A4B Q4_K_M — Vulkan pp2048/tg128 benchmark
# Copy of bench-luffy-q4-rocmfp4.sh, pointed at llama-official.

BENCH_EXE="/home/rodri/Desktop/llama-official/build/bin/llama-bench"
MODEL_PATH="/run/media/rodri/AI/models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"

for f in "$BENCH_EXE" "$MODEL_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  -lm none \
  -p 2048 \
  -n 128 \
  -b 2048 \
  -ub 512 \
  -fa 1 \
  -sm layer \
  -ts 50/50 \
  -ngl 99 \
  -ctk q4_0 \
  -ctv q4_0 \
  2>&1 | tee "$HOME/Desktop/bench-gemma-vulkan-$(date +%Y%m%d-%H%M%S).txt"

echo
read -r -p "Press [Enter] key to exit..."
