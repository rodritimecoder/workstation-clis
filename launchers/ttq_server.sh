#!/usr/bin/env bash
# TTQ Server — Qwen3.6-35B-A3B Uncensored HauhauCS Aggressive (TTQ-4.51bpw-IQ4_NL)
# Multi-GPU Vulkan server with deepseek reasoning and 128K context window

DRIVE="/run/media/rodri/AI"
SERVER_EXE="${SRV_EXE:-$DRIVE/llama.cpp/build/bin/llama-server}"
if [ ! -f "$SERVER_EXE" ]; then
  SERVER_EXE="$DRIVE/ROCmFPX/build-vulkan-linux/bin/llama-server"
fi


MODEL_DIR="$DRIVE/models/TokenTinkerer/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-TTQ-GGUF"
MODEL_PATH="${SRV_MODEL:-$MODEL_DIR/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-TTQ-4.51bpw-IQ4_NL.gguf}"
TEMPLATE_PATH="$DRIVE/models/froggeric/Qwen-Fixed-Chat-Templates/chat_template.jinja"

HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"
CTX="${CTX:-131072}"
NOMMAP="${NOMMAP:-1}"

for f in "$SERVER_EXE" "$MODEL_PATH" "$TEMPLATE_PATH"; do
  if [ ! -f "$f" ]; then
    echo "Missing required file: $f"
    read -r -p "Press [Enter] key to exit..."
    exit 1
  fi
done

MMFLAG=()
if [ "$NOMMAP" = "1" ]; then
  if "$SERVER_EXE" --help 2>&1 | grep -q -- "-lm"; then
    MMFLAG=(-lm none)
  else
    MMFLAG=(--no-mmap)
  fi
fi

MTP_PATH="${MTP_PATH:-$MODEL_DIR/Qwen3.6-35B-A3B-MTP-ONLY-Q4_K_M-shared.gguf}"
MTP_FLAGS=()
if [ -f "$MTP_PATH" ]; then
  echo "MTP drafter: $(basename "$MTP_PATH") (n_max=2)"
  MTP_FLAGS=(
    -md "$MTP_PATH"
    -ngld 999
    -ctkd q8_0
    -ctvd q8_0
    --spec-type draft-mtp
    --spec-draft-n-max 2
  )
fi

echo "Loading $(du -h "$MODEL_PATH" | cut -f1) model: $(basename "$MODEL_PATH")..."
echo "backend   : Vulkan Dual-GPU (45/55 split)"
echo "mmap      : ${MMFLAG[*]:-enabled (pageable)}"
echo "ctx       : $CTX"
echo "Serving on http://$HOST:$PORT"
echo


if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "WARNING: port $PORT is already in use — another server is probably running."
  echo "         Stop it, or rerun with:  LLAMA_PORT=8086 $0"
fi

"$SERVER_EXE" \
  -m "$MODEL_PATH" \
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
  "${MMFLAG[@]}" \
  "${MTP_FLAGS[@]}" \
  "$@"


echo
read -r -p "Press [Enter] key to exit..."
