#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/home/rodri/Avalon-models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-GGUF}"
SERVER="${LLAMA_SERVER_BIN:-${HOME}/build/llama.cpp-ggml/build-rocm/bin/llama-server}"
MODEL="${LLAMA_MODEL:-${MODEL_DIR}/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf}"
FAST_MTP="${FAST_MTP:-${MODEL_DIR}/MTP/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf}"
STATIC_PATH="${LLAMA_STATIC_PATH:-${HOME}/build/llama.cpp-src/build/tools/ui/dist}"
HOST="${LLAMA_HOST:-0.0.0.0}"
PORT="${LLAMA_PORT:-8080}"
CTX="${LLAMA_CONTEXT:-131072}"
BATCH="${LLAMA_BATCH:-2048}"
UBATCH="${LLAMA_UBATCH:-512}"
SPEC_MODE="${SPEC_MODE:-mtp}"
DRAFT_N_MAX="${DRAFT_N_MAX:-4}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"

export LD_LIBRARY_PATH="/opt/rocm/core-10.0/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

case "$SPEC_MODE" in
  fastmtp)
    printf 'WARNING: FastMTP-32K is a vocab-pruned draft (output.weight 32768 vs token_embd 248320, d2t I32).\nThis llama.cpp build (0.8.0-dev) validates the draft head against the target vocab and rejects it;\nthe embedded MTP head is the working path (SPEC_MODE=mtp). Keeping this branch for a build that applies d2t.\n' >&2
    SPEC_ARGS=(-md "$FAST_MTP" --spec-type draft-mtp --spec-draft-n-max "$DRAFT_N_MAX")
    ;;
  mtp)
    SPEC_ARGS=(--spec-type draft-mtp --spec-draft-n-max "$DRAFT_N_MAX")
    ;;
  none)
    SPEC_ARGS=(--spec-type none)
    ;;
  *)
    printf 'Unsupported SPEC_MODE: %s (use fastmtp, mtp or none)\n' "$SPEC_MODE" >&2
    exit 2
    ;;
esac

case "$REASONING_EFFORT" in
  xhigh|medium|low) REASONING_ARGS=(--reasoning-format deepseek --reasoning on --reasoning-effort "$REASONING_EFFORT") ;;
  off) REASONING_ARGS=(--reasoning-format deepseek --reasoning off --reasoning-budget 0) ;;
  *)
    printf 'Unsupported REASONING_EFFORT: %s (use xhigh, medium, low or off)\n' "$REASONING_EFFORT" >&2
    exit 2
    ;;
esac

for pair in "CTX:$CTX" "BATCH:$BATCH" "UBATCH:$UBATCH" "DRAFT_N_MAX:$DRAFT_N_MAX"; do
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

files=("$SERVER" "$MODEL")
if [[ "$SPEC_MODE" == fastmtp ]]; then
  files+=("$FAST_MTP")
fi
for file in "${files[@]}"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

EXTRA_ARGS=()
if [[ -n "$STATIC_PATH" && -d "$STATIC_PATH" ]]; then
  EXTRA_ARGS+=(--path "$STATIC_PATH")
fi

printf 'Model: %s\nBackend: ROCm 10 (HIP)\nDevices: ROCm0,ROCm1 (tensor split 50/50, fit off)\nContext: %s | Spec: %s (draft n-max %s) | KV: q4_0/q4_0 | batch/ubatch: %s/%s\nReasoning: %s | Sampling: temp 1.0, top-k 20, top-p 0.95, min-p 0.0\nServing: http://%s:%s\n' \
  "$MODEL" "$CTX" "$SPEC_MODE" "$DRAFT_N_MAX" "$BATCH" "$UBATCH" "$REASONING_EFFORT" "$HOST" "$PORT"
if [[ "$SPEC_MODE" == fastmtp ]]; then
  printf 'Draft: %s\n' "$FAST_MTP"
fi
if [[ -n "$STATIC_PATH" && -d "$STATIC_PATH" ]]; then
  printf 'WebUI: %s\n' "$STATIC_PATH"
fi


exec "$SERVER" \
  -m "$MODEL" \
  "${SPEC_ARGS[@]}" \
  --host "$HOST" \
  --port "$PORT" \
  "${EXTRA_ARGS[@]}" \
  -c "$CTX" \
  -dev ROCm0,ROCm1 \
  -sm tensor \
  -ts 50,50 \
  -mg 0 \
  -ngl all \
  --fit off \
  -np 1 \
  -b "$BATCH" \
  -ub "$UBATCH" \
  -fa on \
  --jinja \
  "${REASONING_ARGS[@]}" \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --temp 1.0 \
  --top-k 20 \
  --top-p 0.95 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --n-predict 32768 \
  "$@"
