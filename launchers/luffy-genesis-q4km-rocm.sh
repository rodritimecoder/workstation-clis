#!/usr/bin/env bash
# Luffy Genesis (Qwen3.6-35B-A3B Uncensored Genesis Final, Q4_K_M) — ggml-org
# llama.cpp on ROCm 10. Tensor split across both RX 9060 XTs, fit off.
# No MTP heads in this checkpoint, so spec defaults to none.
set -euo pipefail

AI_ROOT="/run/media/rodri/AI"
SERVER="${SERVER:-${HOME}/build/llama.cpp-ggml/build-rocm/bin/llama-server}"
TARGET="${AI_ROOT}/models/LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-GGUF/Qwen3.6-35B-A3B-Uncensored-Genesis-Final-Q4_K_M.gguf"
TEMPLATE="${TEMPLATE:-${AI_ROOT}/models/froggeric/Qwen-Fixed-Chat-Templates/chat_template.jinja}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
CTX="${CTX:-131072}"
BATCH="${BATCH:-2048}"
UBATCH="${UBATCH:-512}"
SPEC_MODE="${SPEC_MODE:-none}"
DRAFT_N_MAX="${DRAFT_N_MAX:-4}"

export LD_LIBRARY_PATH="/opt/rocm/core-10.0/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

case "$SPEC_MODE" in
  draft-mtp) SPEC_ARGS=(--spec-type draft-mtp --spec-draft-n-max "$DRAFT_N_MAX") ;;
  none)      SPEC_ARGS=(--spec-type none) ;;
  *)
    printf 'Unsupported SPEC_MODE: %s (use draft-mtp or none)\n' "$SPEC_MODE" >&2
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

for file in "$SERVER" "$TARGET" "$TEMPLATE"; do
  if [[ ! -f "$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Target: %s\nBackend: ggml-org llama.cpp / ROCm 10 (HIP)\nDevices: ROCm0,ROCm1 (tensor split 50/50, fit off)\nContext: %s | KV: q4_0/q4_0 | Spec: %s | batch/ubatch: %s/%s | template: %s\nListening: %s:%s\n' \
  "$TARGET" "$CTX" "$SPEC_MODE" "$BATCH" "$UBATCH" "$TEMPLATE" "$HOST" "$PORT"

exec "$SERVER" \
  -m "$TARGET" \
  "${SPEC_ARGS[@]}" \
  --jinja \
  --chat-template-file "$TEMPLATE" \
  --reasoning off \
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
  -t 4 \
  -tb 4 \
  --temp 0.7 \
  --top-p 0.8 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 1.5 \
  --host "$HOST" \
  --port "$PORT"
