#!/usr/bin/env bash
# LFM3-1.7B-Uncensored-AD Q4_K_M — Vulkan vs ROCm pp/tg benchmark
# Target deployment settings: q8_0 KV cache, flash attention, single GPU.
# The 1.7B fits on one 16 GB card, so no tensor split.
# ROCm build: /home/rodri/build/llama.cpp-ggml/build-rocm (Oct 30, same as the
# dual-GPU server scripts). Vulkan build: /run/media/rodri/AI/llama.cpp/build-vulkan (Oct 29).
# LD_LIBRARY_PATH is required for ROCm: not in ldconfig on this system.

VULKAN_BENCH="/run/media/rodri/AI/llama.cpp/build-vulkan/bin/llama-bench"
ROCM_BENCH="/home/rodri/build/llama.cpp-ggml/build-rocm/bin/llama-bench"
ROCM_LIB="/opt/rocm/core-10.0/lib"
MODEL_PATH="/run/media/rodri/AI/models/AtomicChat/LFM3-1.7B-Uncensored-GGUF/LFM3-1.7B-Uncensored-AD-Q4_K_M.gguf"

for f in "$VULKAN_BENCH" "$ROCM_BENCH" "$MODEL_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

OUT="$HOME/Desktop/bench-lfm3-1.7b-vulkan-vs-rocm-$(date +%Y%m%d-%H%M%S).txt"

run_backend() {
  local name="$1" bench="$2" dev="$3"
  echo "=== $name ===" | tee -a "$OUT"
  "$bench" \
    -m "$MODEL_PATH" \
    -p 2048 \
    -n 128,512 \
    -ngl 99 \
    -fa 1 \
    -ctk q8_0 \
    -ctv q8_0 \
    -dev "$dev" \
    -r 3 \
    2>&1 | tee -a "$OUT"
  echo | tee -a "$OUT"
}

echo "Results -> $OUT"
run_backend "Vulkan (RADV GFX1200, device 0)" "$VULKAN_BENCH" Vulkan0

export LD_LIBRARY_PATH="$ROCM_LIB:$ROCM_BENCH/../lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
run_backend "ROCm (HIP GFX1200, device 0)" "$ROCM_BENCH" ROCm0

echo
read -r -p "Press [Enter] key to exit..."
