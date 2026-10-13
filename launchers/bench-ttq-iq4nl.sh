#!/usr/bin/env bash
# TTQ IQ4_NL — Vulkan pp2048/tg128 benchmark
# Runs llama-bench for prompt processing (pp2048) and text generation (tg128)
# with the dual-GPU Vulkan layer-split settings used by the server.

DRIVE="/run/media/rodri/AI"
BENCH_EXE="${DRIVE}/llama.cpp/build/bin/llama-bench"
if [ ! -f "$BENCH_EXE" ]; then
  BENCH_EXE="${DRIVE}/ROCmFPX/build-vulkan-linux/bin/llama-bench"
fi


MODEL_DIR="${DRIVE}/models/TokenTinkerer/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-TTQ-GGUF"
MODEL_PATH="${MODEL_DIR}/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-TTQ-4.51bpw-IQ4_NL.gguf"

OUT_DIR="$HOME/Desktop/ROCmFPX"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/bench-ttq-iq4nl-$(date +%Y%m%d-%H%M%S).txt"

for f in "$BENCH_EXE" "$MODEL_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing required file: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

echo "Model : $(basename "$MODEL_PATH") ($(du -h "$MODEL_PATH" | cut -f1))"
echo "Benchmarking TTQ IQ4_NL on Vulkan (pp2048 / tg128)..."
echo "Report will be saved to: $OUT_FILE"
echo

MMFLAG=()
if "$BENCH_EXE" --help 2>&1 | grep -q -- "-lm"; then
  MMFLAG=(-lm none)
else
  MMFLAG=(-mmp 0)
fi

"$BENCH_EXE" \
  -m "$MODEL_PATH" \
  "${MMFLAG[@]}" \
  -p 2048 \

  -n 128 \
  -b 2048 \
  -ub 512 \
  -fa 1 \
  -sm layer \
  -ts 45/55 \
  -ngl 99 \
  -ctk q4_0 \
  -ctv q4_0 \
  2>&1 | tee "$OUT_FILE"

echo
read -r -p "Press [Enter] key to exit..."
