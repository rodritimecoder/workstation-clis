#!/usr/bin/env bash
# Luffy Q4_0_ROCMFP4 — Vulkan pp2048/tg128 benchmark
# Linux port of bench1.bat
#
# Runs llama-bench for prompt processing (pp2048) and text generation (tg128)
# with the exact settings the server uses. Takes a few minutes.
# Close this window or press Ctrl+C to stop.

DRIVE="/run/media/rodri/AI"
BENCH_EXE="${DRIVE}/ROCmFPX/build-vulkan-linux/bin/llama-bench"
MODEL_GLOB="${DRIVE}/models/LuffyTheFox/*GGUF/*ROCMFP4.gguf"

# Resolve the model via glob (avoids typing a long path).
MODEL_PATH="$(ls -1 $MODEL_GLOB 2>/dev/null | head -1)"

if [ ! -f "$BENCH_EXE" ]; then
  echo "Missing: $BENCH_EXE"
  read -r -p "Press [Enter] key to exit..."
  exit 1
fi

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
  echo "Missing model matching: $MODEL_GLOB"
  read -r -p "Press [Enter] key to exit..."
  exit 1
fi

echo "Model: $MODEL_PATH"

echo "Benchmarking 22G Q4_0_ROCMFP4 on Vulkan (pp2048 / tg128)..."
echo

"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  -mmp 0 \
  -p 2048 \
  -n 128 \
  -b 2048 \
  -ub 512 \
  -fa 1 \
  -sm layer \
  -ts 45/55 \
  -ngl 99 \
  -ctk q4_0 \
  -ctv q4_0

echo
read -r -p "Press [Enter] key to exit..."
