#!/usr/bin/env bash
# h2o.sh — h2o-lightning-4b (4B) decision & visual grounding model
#
# llama.cpp has no backend for `qwen35.decision.type=h2o-lightning`: every
# stock llama-server build rejects this GGUF at load with "unsupported decision
# model type". The decision head and the box readout live in h2oai's shim, so
# this launcher drives `h2o-serve`, which pins its own llama.cpp backend on the
# private port the manifest already declares (:8621).

set -uo pipefail

PORT="${PORT:-8083}"
BACKEND="${DECISION_BACKEND:-vulkan}"
VARIANT="${DECISION_VARIANT:-Q8_0}"
RESTART="${DECISION_RESTART:-0}"
SHIM="${H2O_SERVE:-$(command -v h2o-serve 2>/dev/null)}"
[ -n "$SHIM" ] || SHIM="/run/media/rodri/AI/skills/multimodal/clip-box/scripts/h2o_serve.py"

[ -f "$SHIM" ] || { echo "missing h2o-serve: $SHIM"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  echo "   Set DECISION_RESTART=1 to take the port over from it."
  exit 0
fi

ARGS=(--backend "$BACKEND" --variant "$VARIANT" --port "$PORT")
[ "$RESTART" = "1" ] && ARGS+=(--restart)

echo "🚀 Starting h2o-lightning-4b shim on http://127.0.0.1:${PORT}"
echo "   decisions: /v1/systemone (noul, choice, score), box readout: enabled"
echo "   variant: ${VARIANT}, backend: ${BACKEND}, private llama.cpp on the declared backend port"

if [ -x "$SHIM" ]; then
  exec "$SHIM" "${ARGS[@]}"
fi
exec python3 "$SHIM" "${ARGS[@]}"
