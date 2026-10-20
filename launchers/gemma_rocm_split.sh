#!/usr/bin/env bash
# Gemma official model, llama.cpp built for ROCm (HIP) on gfx1200, tensor-split
# across BOTH GPUs.
#
# ROCm libs are not in ldconfig, so LD_LIBRARY_PATH is set here.
# Start audio.cpp etc. on other ports; this one listens on 8080.

SERVER_EXE="/home/rodri/Desktop/llama-official/build-rocm/bin/llama-server"
MODEL_PATH="/run/media/rodri/AI/models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"
ROCM_LIB="/home/rodri/rocm-hip-dev/lib"

export LD_LIBRARY_PATH="$ROCM_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Tensor split: fraction of the model offloaded to each GPU. Both cards are
# 16 GB, so 1,1 is an even split. Use 3,1 / 1,3 to favour one card.
TENSOR_SPLIT="${TENSOR_SPLIT:-1,1}"
PORT="${PORT:-8080}"

echo "llama-server (ROCm) -> http://127.0.0.1:${PORT}"
echo "  tensor-split : ${TENSOR_SPLIT}"
echo "  model        : $(basename "$MODEL_PATH")"
echo

exec "$SERVER_EXE" \
  -m "$MODEL_PATH" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --reasoning off \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -sm layer \
  -ts "$TENSOR_SPLIT" \
  -c 262144 \
  -b 2048 \
  -ub 512 \
  --cont-batching \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  -fa on \
  -t 8 \
  -tb 8 \
  --temp 0.6 \
  --top-k 64 \
  --top-p 0.9 \
  --min-p 0.05 \
  --repeat-penalty 1.1
