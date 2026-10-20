#!/usr/bin/env bash
# Gemma official model, llama.cpp Vulkan build, BOTH GPUs, split-mode layer.
# No -ts: layers are laid out sequentially across the two cards rather than
# being divided by the tensor-split ratio.

SERVER_EXE="/home/rodri/Desktop/llama-official/build/bin/llama-server"
MODEL_PATH="/run/media/rodri/AI/models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"

# Split mode. "layer" spreads the model across every available device in
# sequence; "row"/"tensor" divide it by the -ts ratio instead.
SPLIT_MODE="${SPLIT_MODE:-layer}"
PORT="${PORT:-8080}"

echo "llama-server (Vulkan) -> http://127.0.0.1:${PORT}"
echo "  split-mode   : ${SPLIT_MODE} across 2 GPUs (no -ts)"
echo "  model        : $(basename "$MODEL_PATH")"
echo

exec "$SERVER_EXE" \
  -m "$MODEL_PATH" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --reasoning off \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -sm "$SPLIT_MODE" \
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
