#!/usr/bin/env bash
# startlux-decision.sh — StartLux-Decision-v1.1-4B-Instant behind the TypeSafe API on :8083
#
# One slot, two processes:
#   :8082  llama-server       the Instant model: non-causal attention, one micro-batch per prompt
#   :8083  startlux-decide    /v1/systemone — prompt layout, option read-out, temperatures
#
# The GGUF holds the text decoder only. The read-out that turns logits into a
# calibrated probability over every option lives in the package, which reads the
# tokenizer, config.json and decision_config.json from the BF16 folder.
#
# Prompts are read in one piece, so -ub is the longest prompt that fits. The
# default 8192 keeps the engine at ~8 GB of VRAM; the published 16384 costs
# ~12.5 GB because the micro-batch buffers scale with it.

set -uo pipefail

DRIVE="/run/media/rodri/AI"
SERVER="${STARTLUX_SERVER:-$DRIVE/llama.cpp/build-vulkan/bin/llama-server}"
GGUF_DIR="${STARTLUX_GGUF_DIR:-$DRIVE/models/startlux-models/StartLux-Decision-v1.1-4B-Instant-GGUF}"
MODEL_DIR="${STARTLUX_MODEL_DIR:-$DRIVE/models/startlux-models/StartLux-Decision-v1.1-4B-Instant}"
PACKAGE="${STARTLUX_PACKAGE:-$HOME/src/StartLux-Decision}"
DECIDE="${STARTLUX_DECIDE:-$PACKAGE/.venv/bin/startlux-decide}"

MODEL="$GGUF_DIR/StartLux-Decision-v1.1-4B-Instant-Q4_K_M.gguf"
MMPROJ="$GGUF_DIR/mmproj-StartLux-Decision-v1.1-4B-Instant-F16.gguf"

PORT="${PORT:-8083}"
BACKEND_PORT="${STARTLUX_BACKEND_PORT:-8082}"
CTX="${CTX:-8192}"
UB="${UB:-8192}"
NGPU="${NGPU:-99}"
RESTART="${STARTLUX_RESTART:-0}"
ENGINE_LOG="${STARTLUX_LOG:-/tmp/startlux-engine.log}"

for f in "$SERVER" "$MODEL" "$MMPROJ" "$DECIDE" "$MODEL_DIR/decision_config.json"; do
  [ -e "$f" ] || { echo "missing: $f"; exit 1; }
done

stop_port() {
  for pid in $(lsof -ti tcp:"$1" 2>/dev/null); do
    kill "$pid" 2>/dev/null && echo "stopped pid $pid on :$1"
  done
}

if [ "$RESTART" = "1" ]; then
  stop_port "$PORT"; stop_port "$BACKEND_PORT"; sleep 3
fi

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️  Something is already answering on ${PORT}."
  echo "   Set STARTLUX_RESTART=1 to take the port over from it."
  exit 0
fi

BACKEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null
    wait "$BACKEND_PID" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM

echo "🚀 StartLux-Decision-v1.1-4B-Instant (Q4_K_M, Q8_0 recommended upstream) — llama.cpp backend"
echo "   engine :${BACKEND_PORT}  ctx ${CTX}  micro-batch ${UB}  prompt attention: bidirectional"
echo "   api    :${PORT}/v1/systemone"
echo

"$SERVER" -m "$MODEL" --mmproj "$MMPROJ" \
  -ngl "$NGPU" -fa on --parallel 1 -c "$CTX" -b "$UB" -ub "$UB" \
  --ctx-checkpoints 0 --cache-ram 0 \
  --image-min-tokens 64 --image-max-tokens 1024 \
  -ctk q8_0 -ctv q8_0 \
  --host 127.0.0.1 --port "$BACKEND_PORT" --no-webui \
  >> "$ENGINE_LOG" 2>&1 &
BACKEND_PID=$!

for _ in $(seq 1 90); do
  curl -fsS -m 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1 && break
  kill -0 "$BACKEND_PID" 2>/dev/null || { echo "engine died — see $ENGINE_LOG"; exit 1; }
  sleep 2
done

if ! curl -fsS -m 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
  echo "engine did not answer on :${BACKEND_PORT} within 180s — see $ENGINE_LOG"
  exit 1
fi

STARTLUX_LLAMACPP_BIDIR=server "$DECIDE" serve \
  --model "$MODEL_DIR" \
  --backend llamacpp \
  --llamacpp-url "http://127.0.0.1:${BACKEND_PORT}" \
  --host 127.0.0.1 \
  --port "$PORT"
