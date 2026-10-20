#!/usr/bin/env bash
# vllm-d3-mini.sh — Premier Jev decision server (native /v1/systemone)
#
# Model: ggml-org/vllm-d3-mini-GGUF (Q4_K_M, 5B, qwen35 arch)
# Vision: mmproj-vllm-d3-mini-Q8_0.gguf
# Port: 8083 (premier decision port) or custom via PORT env var
#
# Requires llama.cpp build >= b11729 (0.7.0-dev); older builds lack both the
# /v1/systemone endpoint (PR #29818) and the vllm-d3 model family (PR #30383).
# Decision models disable prompt caching automatically, so no flags are needed.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
# Prefer an explicit override, else the pinned upstream Vulkan build.
SERVER="${LLAMA_SERVER:-$DRIVE/llama-b11729-bin-ubuntu-vulkan-x64/llama-b11729/llama-server}"
MODELS="$DRIVE/models/ggml-org/vllm-d3-mini-GGUF"

PORT="${PORT:-8083}"
CTX="${CTX:-8192}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/vllm-d3-mini-Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/mmproj-vllm-d3-mini-Q8_0.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "Stop it first, or use PORT=8087"
  exit 0
fi

echo "🚀 Starting vllm-d3-mini on http://127.0.0.1:${PORT} (ctx ${CTX}, vision mmproj enabled)..."
echo "Model: $(basename "$MODEL") + $(basename "$MMPROJ")"
echo "API:   POST /v1/systemone  (choice | score | noul)"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl 99 \
  -c "$CTX" \
  -b 2048 \
  -ub 512 \
  --no-warmup
