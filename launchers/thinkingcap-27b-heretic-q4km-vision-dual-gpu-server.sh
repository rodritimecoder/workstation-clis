#!/usr/bin/env bash
# ThinkingCap Qwen3.6-27B (Q4_K_M + f16 mmproj) — bottlecapai
# llama.cpp on ROCm 10. Tensor split across both RX 9060 XTs, fit off.
# Includes a NextN/MTP head; draft-mtp is enabled by default. Vision needs the mmproj.
set -euo pipefail

AI_ROOT="/run/media/rodri/AI"
SERVER="${SERVER:-${HOME}/build/llama.cpp-ggml/build-rocm/bin/llama-server}"
MODEL_DIR="${MODEL_DIR:-${AI_ROOT}/models/bottlecapai/ThinkingCap-Qwen3.6-27B-GGUF}"
TARGET="${TARGET:-${MODEL_DIR}/ThinkingCap-Qwen3.6-27B-Q4_K_M.gguf}"
MMPROJ="${MMPROJ:-${MODEL_DIR}/mmproj-ThinkingCap-Qwen3.6-27B-f16.gguf}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
CTX="${CTX:-131072}"
BATCH="${BATCH:-2048}"
UBATCH="${UBATCH:-512}"
VISION="${VISION:-1}"
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"
REASONING="${REASONING:-auto}"
SPEC_MODE="${SPEC_MODE:-draft-mtp}"
DRAFT_N_MAX="${DRAFT_N_MAX:-8}"

export LD_LIBRARY_PATH="/opt/rocm/core-10.0/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

case "$SPEC_MODE" in
  draft-mtp) SPEC_ARGS=(--spec-type draft-mtp --spec-draft-n-max "$DRAFT_N_MAX") ;;
  none)      SPEC_ARGS=(--spec-type none) ;;
  *)
    printf 'Unsupported SPEC_MODE: %s (use draft-mtp or none)\n' "$SPEC_MODE" >&2
    exit 2
    ;;
esac

case "$REASONING" in
  on|off|auto) REASONING_ARGS=(--reasoning "$REASONING") ;;
  *)
    printf 'Unsupported REASONING: %s (use on, off or auto)\n' "$REASONING" >&2
    exit 2
    ;;
esac

case "$VISION" in
  1) VISION_ARGS=(--mmproj "$MMPROJ" --mmproj-offload --image-min-tokens "$IMAGE_MIN_TOKENS") ;;
  0) VISION_ARGS=() ;;
  *)
    printf 'Unsupported VISION: %s (use 1 or 0)\n' "$VISION" >&2
    exit 2
    ;;
esac

for pair in "PORT:$PORT" "CTX:$CTX" "BATCH:$BATCH" "UBATCH:$UBATCH" "IMAGE_MIN_TOKENS:$IMAGE_MIN_TOKENS" "DRAFT_N_MAX:$DRAFT_N_MAX"; do
  name="${pair%%:*}"
  value="${pair#*:}"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    printf '%s must be a positive integer\n' "$name" >&2
    exit 2
  fi
done
if ((UBATCH > BATCH)); then
  printf 'UBATCH (%s) cannot exceed BATCH (%s)\n' "$UBATCH" "$BATCH" >&2
  exit 2
fi
if ((DRAFT_N_MAX > 8)); then
  printf 'DRAFT_N_MAX (%s) exceeds the supported ceiling of 8; 12+ aborts in ggml_new_object\n' "$DRAFT_N_MAX" >&2
  exit 2
fi

REQUIRED=("$SERVER" "$TARGET")
if [[ "$VISION" == 1 ]]; then
  REQUIRED+=("$MMPROJ")
fi
for file in "${REQUIRED[@]}"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Target: %s\nBackend: ggml-org llama.cpp / ROCm 10 (HIP)\nDevices: ROCm0,ROCm1 (tensor split 50/50, fit off)\nSpec: %s | draft n-max: %s | MTP head is part of the model GGUF\nContext: %s | KV: q4_0/q4_0 | Vision: %s (min %s img tokens) | Reasoning: %s | batch/ubatch: %s/%s\nListening: %s:%s\n' \
  "$TARGET" "$SPEC_MODE" "$DRAFT_N_MAX" "$CTX" "$VISION" "$IMAGE_MIN_TOKENS" "$REASONING" "$BATCH" "$UBATCH" "$HOST" "$PORT"

exec "$SERVER" \
  -m "$TARGET" \
  "${VISION_ARGS[@]}" \
  "${SPEC_ARGS[@]}" \
  --jinja \
  --reasoning-format deepseek \
  "${REASONING_ARGS[@]}" \
  -dev ROCm0,ROCm1 \
  -sm tensor \
  -ts 50,50 \
  -mg 0 \
  -ngl all \
  --fit off \
  -c "$CTX" \
  -np 1 \
  -b "$BATCH" \
  -ub "$UBATCH" \
  -ctk q4_0 \
  -ctv q4_0 \
  -fa on \
  --temp 0.7 \
  --top-p 0.8 \
  --top-k 20 \
  --min-p 0.0 \
  --host "$HOST" \
  --port "$PORT" \
  "$@"
