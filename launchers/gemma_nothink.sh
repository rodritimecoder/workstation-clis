#!/usr/bin/env bash

SERVER_EXE="/run/media/rodri/AI/ROCmFPX/build-vulkan-linux/bin/llama-server"
MODEL_PATH="/run/media/rodri/AI/models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"

"$SERVER_EXE" \
  -m "$MODEL_PATH" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --reasoning off \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 99 \
  -sm layer \
  -ts 45/55 \
  -c 262144 \
  -b 2048 \
  -ub 512 \
  --cont-batching \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  -fa on \
  -t 4 \
  -tb 4 \
  --temp 0.6 \
  --top-k 64 \
  --top-p 0.9 \
  --min-p 0.05 \
  --repeat-penalty 1.1

read -p "Press [Enter] key to exit..."
