#!/usr/bin/env bash
# gliclass-edge.sh — knowledgator/gliclass-v4-edge (0.4B) zero-shot decision & routing model
# Runs on CPU + ONNX in ~600 MB RAM (0 VRAM). Answers native /v1/systemone (bool, choice, score)
# at ~26 ms median latency. Ideal low-memory candidate for Kem evaluation loops.

set -uo pipefail

PORT="${PORT:-8083}"
VARIANT="${GLICLASS_VARIANT:-q8}"
THREADS="${GLICLASS_THREADS:-4}"
SERVER="/home/rodri/gliclass-server/server.py"
PYTHON="/home/rodri/.venvs/gliclass/bin/python"

[ -f "$SERVER" ] || { echo "missing server: $SERVER"; exit 1; }
[ -x "$PYTHON" ] || { echo "missing python in venv: $PYTHON"; exit 1; }

if curl -fsS -m 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ Something is already answering on ${PORT}."
  exit 0
fi

echo "🚀 Starting GLiClass v4 Edge ONNX on http://127.0.0.1:${PORT}"
echo "   decisions: /v1/systemone (bool, choice, score)"
echo "   variant: ${VARIANT}, backend: CPUExecutionProvider (ONNX, ${THREADS} threads, 0 VRAM)"

exec "$PYTHON" "$SERVER" --host 127.0.0.1 --port "$PORT" --variant "$VARIANT" --threads "$THREADS"
