#!/usr/bin/env bash
# Gemma 4 26B-A4B Q4_K_M — ROCm pp2048/tg128 benchmark
# Copy of bench-luffy-q4-rocmfp4.sh, pointed at llama-official ROCm build.
# LD_LIBRARY_PATH is required: ROCm is not in ldconfig on this system.

BENCH_EXE="/home/rodri/Desktop/llama-official/build-rocm/bin/llama-bench"
ROCM_LIB="/home/rodri/rocm-hip-dev/lib"
MODEL_PATH="/run/media/rodri/models/models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"

for f in "$BENCH_EXE" "$MODEL_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

export LD_LIBRARY_PATH="$ROCM_LIB:$BENCH_EXE/../bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"


"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  -lm none \
  -p 2048,8192 \
  -n 128 \
  -b 2048 \
  -ub 512 \
  -fa 1 \
  -sm layer \
  -ts 50/50 \
  -ngl 99 \
  -ctk q4_0 \
  -ctv q4_0 \
  2>&1 | tee "$HOME/Desktop/bench-gemma-rocm-$(date +%Y%m%d-%H%M%S).txt"

echo
read -r -p "Press [Enter] key to exit..."
