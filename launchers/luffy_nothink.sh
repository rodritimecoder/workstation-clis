#!/usr/bin/env bash
# Luffy (Qwen3.6-35B-A3B Uncensored Genesis Final) — no-thinking mode
# Linux port of luffy_nothink.bat
#
# Close this window or press Ctrl+C to stop the server.

DRIVE="/run/media/rodri/AI"
SERVER_EXE="${SRV_SERVER:-$DRIVE/ROCmFPX/build-vulkan-linux/bin/llama-server}"
MODEL_PATH="${SRV_MODEL:-$DRIVE/models/LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-GGUF/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-Q4_K_M.gguf}"
TEMPLATE_PATH="${SRV_TEMPLATE:-$DRIVE/models/froggeric/Qwen-Fixed-Chat-Templates/chat_template.jinja}"

# Override without editing:  LLAMA_PORT=8082 ./luffy_nothink.sh
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"

for f in "$SERVER_EXE" "$MODEL_PATH" "$TEMPLATE_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

echo "Loading 22G model with --no-mmap, this takes a while..."
echo "Serving on http://$HOST:$PORT  (audio.cpp uses 8081)"

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "WARNING: port $PORT is already in use — another llama-server is probably running."
  echo "         Stop it, or rerun with:  LLAMA_PORT=8082 $0"
fi

"$SERVER_EXE" \
  -m "$MODEL_PATH" \
  --jinja \
  --chat-template-file "$TEMPLATE_PATH" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --no-mmap \
  -np 1 \
  --host "$HOST" \
  --port "$PORT" \
  -ngl 99 \
  -sm layer \
  -ts 45/55 \
  -c 131072 \
  -b 2048 \
  -ub 512 \
  -ctk q4_0 \
  -ctv q4_0 \
  -fa on \
  -t 4 \
  -tb 4 \
  --temp 0.7 \
  --top-p 0.8 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 1.5

echo
read -r -p "Press [Enter] key to exit..."
