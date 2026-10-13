#!/usr/bin/env bash
DRIVE="/run/media/rodri/AI"
SERVER_EXE="$DRIVE/ROCmFPX/build-vulkan-linux/bin/llama-server"
MODEL_DIR="$DRIVE/models/LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-GGUF"
MODEL_PATH="${SRV_MODEL:-$MODEL_DIR/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-Q4_0_ROCMFP4.gguf}"
MMPROJ_PATH="${SRV_MMPROJ:-$MODEL_DIR/mmproj-Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-Final-F16.gguf}"
TEMPLATE_PATH="$DRIVE/models/froggeric/Qwen-Fixed-Chat-Templates/chat_template.jinja"

HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"


CTX="${CTX:-131072}"

NOMMAP="${NOMMAP:-1}"

for f in "$SERVER_EXE" "$MODEL_PATH" "$MMPROJ_PATH" "$TEMPLATE_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

MMFLAG=(--mmproj "$MMPROJ_PATH")
MMFLAG=()
if [ "$NOMMAP" = "1" ]; then MMFLAG+=(--no-mmap); fi

echo "Loading $(du -h "$MODEL_PATH" | cut -f1) model; this takes a while..."
echo "vision    : $(basename "$MMPROJ_PATH")"
echo "mmap      : ${MMFLAG[*]:-enabled (pageable)}"
echo "ctx       : $CTX"
echo "Serving on http://$HOST:$PORT"

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "WARNING: port $PORT is already in use — another llama-server is probably running."
  echo "         Stop it, or rerun with:  LLAMA_PORT=8082 $0"
fi

"$SERVER_EXE" \
  -m "$MODEL_PATH" \
  --mmproj "$MMPROJ_PATH" \
  --jinja \
  --chat-template-file "$TEMPLATE_PATH" \
  --reasoning-format deepseek \
  -np 1 \
  --host "$HOST" \
  --port "$PORT" \
  -ngl 99 \
  -sm layer \
  -ts 45/55 \
  -c "$CTX" \
  -b 2048 \
  -ub 512 \
  -ctk q4_0 \
  -ctv q4_0 \
  -fa on \
  -t 4 \
  -tb 4 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  "${MMFLAG[@]}"

echo
read -r -p "Press [Enter] key to exit..."
