#!/usr/bin/env bash
# crispembed-ocr.sh — CrispEmbed server on port 8084.
#
# Supported Engines:
#   - oxr (recommended): OXR-1.0 document parser — D-FINE layout + per-region
#                        recognition + reading order + Markdown/JSON (POST /oxr/document)
#   - ppocrv6 (Default): PP-OCRv6 small detector (DB++) + small CTC recognizer (q8-head)
#   - parseq:           DBNet ResNet-18 detector + PARSeq scene-text recognizer
#
# Endpoints:
#   - POST /ocr/pipeline  Full detection + recognition pipeline (text, bounding boxes, markdown)
#   - POST /oxr/document  OXR-1.0 document route: {"images": [...], "format": "upstream|markdown"}
#   - GET  /health        Health check endpoint
#
# Usage:
#   sh/crispembed-ocr.sh                  # Starts PP-OCRv6 on Vulkan GPU (port 8084)
#   ENGINE=parseq sh/crispembed-ocr.sh    # Use DBNet + PARSeq engine
#   ENGINE=oxr sh/crispembed-ocr.sh       # OXR-1.0 document parser (Vulkan GPU)
#   ENGINE=oxr OXR_DEVICE=cpu sh/crispembed-ocr.sh   # OXR on CPU (reference arm)
#   PORT=8086 sh/crispembed-ocr.sh        # Custom port
#   BACKEND=cpu sh/crispembed-ocr.sh      # Force CPU backend

set -uo pipefail

DRIVE="/run/media/rodri/AI"
PORT="${PORT:-8084}"
HOST="${HOST:-127.0.0.1}"
BACKEND="${BACKEND:-vulkan}"
ENGINE="${ENGINE:-ppocrv6}"
MODE="${MODE:-pipeline}"

OXR_MODEL="${OXR_MODEL:-$DRIVE/models/cstr/OXR-1.0-GGUF/oxr-1.0-q4_k-head.gguf}"
# Numerically-exact arm: OXR_MODEL=$DRIVE/models/cstr/OXR-1.0-GGUF/oxr-1.0-f16.gguf
OXR_LAYOUT="${OXR_LAYOUT:-$DRIVE/models/cstr/OXR-1.0-DFINE-layout-GGUF/oxr-1.0-dfine-layout-f32.gguf}"
OXR_DEVICE="${OXR_DEVICE:-gpu}"

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

# Check if port is already listening
if curl -fsS -m 2 "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "A service is already responding on http://${HOST}:${PORT}."
  echo "Stop it first or choose another port with PORT=8086 $0"
  exit 0
fi

echo "=========================================================="
echo " CrispEmbed Server"
echo "=========================================================="
echo " Engine:      $ENGINE"
echo " Backend:     $BACKEND"
echo " Server:      $SERVER"
echo " Endpoint:    http://${HOST}:${PORT}"

if [ "$ENGINE" = "oxr" ]; then
  [ -f "$OXR_MODEL" ] || { echo "Error: OXR model missing: $OXR_MODEL"; exit 1; }
  [ -f "$OXR_LAYOUT" ] || { echo "Error: OXR D-FINE layout model missing: $OXR_LAYOUT"; exit 1; }

  export CRISPEMBED_OXR=1
  export CRISPEMBED_ACCEPT_OXR_LICENSE=1
  export CRISPEMBED_OXR_NATIVE_DOC=1
  if [ "$OXR_DEVICE" = "cpu" ]; then
    export CRISPEMBED_OXR_FORCE_CPU=1
    unset CRISPEMBED_OXR_GPU CRISPEMBED_OXR_GPU_FLASH
  else
    export CRISPEMBED_OXR_GPU=1
    # RADV's dense F32 attention path decodes garbage; the native flash kernel is token-exact.
    export CRISPEMBED_OXR_GPU_FLASH=1
    unset CRISPEMBED_OXR_FORCE_CPU
  fi

  echo " Device:      OXR $OXR_DEVICE"
  echo " Recognizer:  $(basename "$OXR_MODEL")"
  echo " Layout:      $(basename "$OXR_LAYOUT")"
  echo "=========================================================="
  echo "Query with:"
  echo "  curl -s -X POST http://${HOST}:${PORT}/oxr/document \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"images\": [\"/path/to/page.png\"], \"format\": \"upstream\"}' | jq ."
  echo "Press Ctrl+C to stop."
  echo

  exec "$SERVER" \
    --oxr-doc-model "$OXR_MODEL" \
    --oxr-doc-layout-model "$OXR_LAYOUT" \
    --host "$HOST" \
    --port "$PORT" \
    "$@"
fi

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

if [ "$MODE" = "pipeline" ]; then
  [ -f "$DET_MODEL" ] || { echo "Error: Detector model missing: $DET_MODEL"; exit 1; }
fi
[ -f "$REC_MODEL" ] || { echo "Error: Recognizer model missing: $REC_MODEL"; exit 1; }

exec "$SERVER" \
  "${ARGS[@]}" \
  --host "$HOST" \
  --port "$PORT" \
  "$@"
