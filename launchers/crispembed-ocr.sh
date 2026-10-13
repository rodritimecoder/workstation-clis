#!/usr/bin/env bash
# crispembed-ocr.sh — CrispEmbed OCR Server on port 8084.
#
# Supported Engines:
#   - ppocrv6 (Default): PP-OCRv6 small detector (DB++) + small CTC recognizer (q8-head)
#   - parseq:           DBNet ResNet-18 detector + PARSeq scene-text recognizer
#
# Endpoints:
#   - POST /ocr/pipeline  Full detection + recognition pipeline (text, bounding boxes, markdown)
#   - GET  /health        Health check endpoint
#
# Usage:
#   sh/crispembed-ocr.sh                  # Starts PP-OCRv6 on Vulkan GPU (port 8084)
#   ENGINE=parseq sh/crispembed-ocr.sh    # Use DBNet + PARSeq engine
#   PORT=8086 sh/crispembed-ocr.sh        # Custom port
#   BACKEND=cpu sh/crispembed-ocr.sh      # Force CPU backend

set -uo pipefail

DRIVE="/run/media/rodri/AI"
PORT="${PORT:-8084}"
HOST="${HOST:-127.0.0.1}"
BACKEND="${BACKEND:-vulkan}"
ENGINE="${ENGINE:-ppocrv6}"
MODE="${MODE:-pipeline}"

# Model paths based on selected engine
if [ "$ENGINE" = "ppocrv6" ]; then
  DET_MODEL="${DET_MODEL:-$DRIVE/models/cstr/PP-OCRv6-small-det-GGUF/PP-OCRv6_small_det-f16.gguf}"
  REC_MODEL="${REC_MODEL:-$DRIVE/models/cstr/PP-OCRv6_small_rec-GGUF/PP-OCRv6_small_rec-q8-head.gguf}"
else
  DET_MODEL="${DET_MODEL:-$DRIVE/models/cstr/dbnet-ic15-GGUF/dbnet-ic15-f16.gguf}"
  REC_MODEL="${REC_MODEL:-$DRIVE/models/cstr/parseq-GGUF/parseq-q8_0.gguf}"
fi

# Select binary
if [ "$BACKEND" = "vulkan" ] && [ -x "$DRIVE/CrispEmbed/build-vulkan/crispembed-server" ]; then
  SERVER="$DRIVE/CrispEmbed/build-vulkan/crispembed-server"
elif [ -x "$DRIVE/CrispEmbed/build-cpu/crispembed-server" ]; then
  SERVER="$DRIVE/CrispEmbed/build-cpu/crispembed-server"
  BACKEND="cpu"
else
  echo "Error: crispembed-server binary not found."
  echo "Expected $DRIVE/CrispEmbed/build-vulkan/crispembed-server or build-cpu/crispembed-server"
  exit 1
fi

# Verify models
[ -f "$REC_MODEL" ] || { echo "Error: Recognizer model missing: $REC_MODEL"; exit 1; }
if [ "$MODE" = "pipeline" ]; then
  [ -f "$DET_MODEL" ] || { echo "Error: Detector model missing: $DET_MODEL"; exit 1; }
fi

# Check if port is already listening
if curl -fsS -m 2 "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "A service is already responding on http://${HOST}:${PORT}."
  echo "Stop it first or choose another port with PORT=8086 $0"
  exit 0
fi

echo "=========================================================="
echo " CrispEmbed OCR Server"
echo "=========================================================="
echo " Engine:      $ENGINE"
echo " Backend:     $BACKEND"
echo " Server:      $SERVER"
echo " Endpoint:    http://${HOST}:${PORT}"
echo " Mode:        $MODE"
if [ "$MODE" = "pipeline" ]; then
  echo " Detector:    $(basename "$DET_MODEL")"
  echo " Recognizer:  $(basename "$REC_MODEL")"
  ARGS=(--ocr-pipeline --ocr-engine "$ENGINE" --ocr-det "$DET_MODEL" --ocr-rec "$REC_MODEL")
else
  echo " Recognizer:  $(basename "$REC_MODEL") (standalone)"
  ARGS=(--ocr "$REC_MODEL")
fi
echo "=========================================================="
echo "Query with:"
if [ "$MODE" = "pipeline" ]; then
  echo "  curl -s -X POST http://${HOST}:${PORT}/ocr/pipeline \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"image\": \"/path/to/image.png\"}' | jq ."
else
  echo "  curl -s -X POST http://${HOST}:${PORT}/ocr/model \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"image\": \"/path/to/crop.png\"}' | jq ."
fi
echo "Press Ctrl+C to stop."
echo

exec "$SERVER" \
  "${ARGS[@]}" \
  --host "$HOST" \
  --port "$PORT" \
  "$@"
