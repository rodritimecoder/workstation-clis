#!/usr/bin/env bash
# decision-model.sh — h2o-lightning-4b (4B) decision & visual grounding model on llama-server
# Min-maxed VRAM profile: 8k context with q4_0 KV cache + tuned 2048 ubatch for Image + Text

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${DECISION_SERVER:-$DRIVE/llama.cpp/build-vulkan/bin/llama-server}"
MODEL_DIR="${DECISION_MODEL_DIR:-$DRIVE/models/h2oai/h2o-lightning-4b-gguf}"
MODEL="$MODEL_DIR/h2o-lightning-4b-Q4_K_M.gguf"
MMPROJ="$MODEL_DIR/mmproj-lightning-f16.gguf"

PORT="${PORT:-8083}"
CTX="${CTX:-8192}"
BATCH="${BATCH:-2048}"
UBATCH="${UBATCH:-2048}"
IMG_TOKENS="${IMG_TOKENS:-1280}"
NGPU="${NGPU:-99}"
RESTART="${DECISION_RESTART:-0}"

[ -x "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model: $MODEL"; exit 1; }

MMPROJ_ARGS=()
[ -f "$MMPROJ" ] && MMPROJ_ARGS=(--mmproj "$MMPROJ" --image-max-tokens "$IMG_TOKENS")

if [ "$RESTART" = "1" ]; then
  for pid in $(lsof -ti tcp:"$PORT" 2>/dev/null); do
    kill "$pid" 2>/dev/null && echo "stopped pid $pid on :${PORT}"
  done
  sleep 2
fi

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "   Set DECISION_RESTART=1 to take the port over from it."
  exit 0
fi

echo "🚀 Starting h2o-lightning-4b (4B, Q4_K_M) on http://127.0.0.1:${PORT}"
echo "   native /v1/systemone, ctx: ${CTX}, batch: ${BATCH}, ubatch: ${UBATCH}"
echo "   KV cache: q4_0 (Key + Value), image budget: ${IMG_TOKENS} tokens"
echo "   vision projector: ${MMPROJ_ARGS[1]:-disabled}"
echo

exec "$SERVER" \
  -m "$MODEL" \
  "${MMPROJ_ARGS[@]}" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl "$NGPU" \
  -c "$CTX" \
  -b "$BATCH" \
  -ub "$UBATCH" \
  -ctk q4_0 \
  -ctv q4_0
