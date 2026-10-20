#!/usr/bin/env bash
# pplx-decider-flash.sh — pplx-decider-flash v1.2 (4B) decision model on llama-server
#
# The v1.2 checkpoint needs non-causal attention: the full-attention layers attend
# over the whole request, so the server must run with causal attention disabled.
# The readout is applied by the client, so the server runs in embedding mode with
# per-token output (pooling none) and the whole request must fit in one ubatch.
#
# llama.cpp build: /run/media/rodri/AI/llama.cpp/build-vulkan (>= 33d6135, decision models)

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${PPLX_SERVER:-$DRIVE/llama.cpp/build-vulkan/bin/llama-server}"
MODEL_DIR="${PPLX_MODEL_DIR:-$DRIVE/models/perplexity-ai/pplx-decider-flash-v1.2}"
MODEL="$MODEL_DIR/pplx-decider-flash-v1.2-Q4_K_M.gguf"
MMPROJ="$MODEL_DIR/mmproj-decider-flash-v1.2-f16.gguf"

PORT="${PORT:-8083}"
CTX="${CTX:-8192}"
NGPU="${NGPU:-99}"
RESTART="${PPLX_RESTART:-0}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ_ARGS=()
[ -f "$MMPROJ" ] && MMPROJ_ARGS=(--mmproj "$MMPROJ")

# The decision slot is shared: stop whatever model currently holds the port
# before taking it. PPLX_RESTART=1 does that unconditionally.
if [ "$RESTART" = "1" ]; then
  for pid in $(lsof -ti tcp:"$PORT" 2>/dev/null); do
    kill "$pid" 2>/dev/null && echo "stopped pid $pid on :${PORT}"
  done
  sleep 3
fi

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "   Set PPLX_RESTART=1 to take the port over from it."
  exit 0
fi

echo "🚀 Starting pplx-decider-flash v1.2 (4B, Q4_K_M) on http://127.0.0.1:${PORT}"
echo "   non-causal attention, embedding mode (pooling none), ctx ${CTX}"
echo "   vision: ${MMPROJ_ARGS[1]:-disabled}"
echo

exec "$SERVER" \
  -m "$MODEL" \
  "${MMPROJ_ARGS[@]}" \
  --override-kv qwen35.attention.causal=bool:false \
  --embeddings \
  --pooling none \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl "$NGPU" \
  -c "$CTX" \
  -b "$CTX" \
  -ub "$CTX" \
  -np 1 \
  --no-webui
