#!/usr/bin/env bash
# decide.sh — rotate the :8083 decision slot between candidate models.
#
#   decide.sh list
#   decide.sh status
#   decide.sh h2o | startlux | pplx | vllm-d3-mini | vllm-d3-nano | imajev
#
# The launchers are model-named; this front door is not, so the command you
# type does not change when the model behind the slot does. It frees the port
# the candidates disagree about (some restart themselves, some refuse) and then
# hands over to the chosen launcher.

set -uo pipefail

SLOT=8083
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

declare -A LAUNCHERS=(
  [h2o]="h2o.sh"
  [startlux]="startlux-decision.sh"
  [pplx]="pplx-decider-flash.sh"
  [vllm-d3-mini]="vllm-d3-mini.sh"
  [vllm-d3-nano]="vllm-d3-nano.sh"
  [imajev]="imajev-decider.sh"
)

served_model() {
  curl -fsS -m 2 "http://127.0.0.1:${SLOT}/v1/models" 2>/dev/null |
    python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("data") or [{}])[0].get("id") or "unknown")' 2>/dev/null
}

case "${1:-list}" in
  list)
    printf 'slot :%s candidates\n' "$SLOT"
    for name in "${!LAUNCHERS[@]}"; do
      printf '  %-14s %s\n' "$name" "${LAUNCHERS[$name]}"
    done | sort
    ;;
  status)
    if curl -fsS -m 2 "http://127.0.0.1:${SLOT}/health" >/dev/null 2>&1; then
      printf ':%s UP  %s\n' "$SLOT" "$(served_model)"
    else
      printf ':%s DOWN\n' "$SLOT"
    fi
    ;;
  *)
    target="${LAUNCHERS[${1:-}]:-}"
    [ -n "$target" ] || { echo "unknown candidate: $1 (try: $0 list)"; exit 2; }
    for pid in $(lsof -ti tcp:"$SLOT" 2>/dev/null); do
      kill "$pid" 2>/dev/null && echo "stopped pid $pid on :$SLOT"
    done
    for _ in $(seq 1 20); do
      lsof -ti tcp:"$SLOT" >/dev/null 2>&1 || break
      sleep 0.5
    done
    if lsof -ti tcp:"$SLOT" >/dev/null 2>&1; then
      echo ":$SLOT is still held; not starting $1"
      exit 1
    fi
    echo "starting $1 on :$SLOT"
    PORT="$SLOT" exec "$HERE/$target"
    ;;
esac
