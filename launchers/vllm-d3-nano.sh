#!/usr/bin/env bash
# vllm-d3-nano.sh — 2.39B Jev decision server (native /v1/systemone)
#
# Model: ggml-org/vllm-d3-nano-GGUF (Q4_K_M, 2.39B, qwen35 arch, non-causal)
# Vision: mmproj-vllm-d3-nano-Q8_0.gguf
# Port: 8083 (decision slot) or custom via PORT env var
#
# Requires llama.cpp build >= b11729 (0.7.0-dev) for the /v1/systemone
# endpoint and the vllm-d3 model family. Decision models disable prompt
# caching automatically, so no caching flags are needed.
#
# The vision budget is n_ubatch / 2, so UB sets how much of a single image
# survives: ub 4096 keeps the full 1600-token budget, ub 2048 silently caps a
# single image at 1024 tokens, ub 512 at 256. UB must stay <= CTX.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${LLAMA_SERVER:-$DRIVE/llama-b11729-bin-ubuntu-vulkan-x64/llama-b11729/llama-server}"
MODELS="$DRIVE/models/ggml-org/vllm-d3-nano-GGUF"

PORT="${PORT:-8083}"
CTX="${CTX:-8192}"
UB="${UB:-4096}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }

MODEL="$MODELS/vllm-d3-nano-Q4_K_M.gguf"
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ="$MODELS/mmproj-vllm-d3-nano-Q8_0.gguf"
[ -f "$MMPROJ" ] || { echo "missing projector: $MMPROJ"; exit 1; }

if [ "$UB" -gt "$CTX" ]; then
  echo "UB ($UB) > CTX ($CTX); llama.cpp would silently clamp ub down to b."
  exit 1
fi

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "Stop it first, or use PORT=8099"
  exit 0
fi

echo "🚀 Starting vllm-d3-nano on http://127.0.0.1:${PORT} (ctx ${CTX}, ub ${UB}, vision enabled)..."
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
  -b "$CTX" \
  -ub "$UB" \
  --no-warmup
