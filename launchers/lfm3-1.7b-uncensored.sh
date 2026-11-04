#!/usr/bin/env bash
# lfm3-1.7b-uncensored.sh — LiquidAI LFM3-1.7B-Uncensored (AD, Q4_K_M) RP server
#
# Bench result 2026-11-04 (bench-lfm3-1.7b-vulkan-vs-rocm.sh): Vulkan tg ~196 t/s
# vs ROCm tg ~176 t/s on one RX 9060 XT — Vulkan wins on the tg-bound RP workload,
# so this launcher pins the Vulkan build. Full bench:
# ~/Desktop/bench-lfm3-1.7b-vulkan-vs-rocm-*.txt
#
# Config: 131072 ctx, q8_0 KV cache (needs flash attention on Vulkan), single GPU.
# Chat template via --jinja from the GGUF's embedded template.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="$DRIVE/llama.cpp/build-vulkan/bin/llama-server"
MODEL="$DRIVE/models/AtomicChat/LFM3-1.7B-Uncensored-GGUF/LFM3-1.7B-Uncensored-AD-Q4_K_M.gguf"

PORT="${PORT:-8091}"
CTX="${CTX:-131072}"
DEV="${DEV:-Vulkan0}"
NP="${NP:-1}"
KV="${KV:-q8_0}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "   Stop it first, or use PORT=... to pick another port."
  exit 0
fi

echo "🚀 LFM3-1.7B-Uncensored-AD (Q4_K_M) on http://127.0.0.1:${PORT}"
echo "   ctx ${CTX} | KV ${KV} | fa on | dev ${DEV} | np ${NP}"
echo "   API: /v1/chat/completions"
echo "Ctrl-C to stop."
echo

exec "$SERVER" \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -c "$CTX" \
  -np "$NP" \
  -ngl 99 \
  -dev "$DEV" \
  -fa on \
  --cache-type-k "$KV" \
  --cache-type-v "$KV" \
  --jinja \
  --reasoning off \
  "$@"
