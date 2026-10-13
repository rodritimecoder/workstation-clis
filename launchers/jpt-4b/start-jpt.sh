#!/usr/bin/env bash
# Launch JPT-4B on stock llama.cpp: engine + System One API + interactive REPL.
#
#   ./start-jpt.sh            engine + API + REPL in this terminal (what the desktop icon runs)
#   ./start-jpt.sh --serve    engine + API only, no REPL, stays in the foreground
#                             (for callers that just want the HTTP endpoint)
#
#   engine  llama-server on JPT_ENGINE_PORT (8090)  — holds the weights, does the prefill
#                                                    (8090 is deliberate: 8080/81/82/83 are taken by LLM/audio/OCR/imajev)
#   API     POST /v1/systemone on JPT_PORT (8082)    — System One wire format (llm2jev-compatible)
#   REPL    typed decisions in this terminal
#
# Close the window, or Ctrl-C / type :quit, to stop everything this script started.
set -uo pipefail

SERVE_ONLY=0
[ "${1:-}" = "--serve" ] && SERVE_ONLY=1

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_BIN="${LLAMA_BIN:-/run/media/rodri/AI/llama.cpp/build/bin}"
GGUF="${JPT_GGUF:-/run/media/rodri/AI/models/prithivMLmods/jpt-4b-GGUF/jpt-4b.Q4_K_M.gguf}"
MMPROJ="${JPT_MMPROJ:-/run/media/rodri/AI/models/prithivMLmods/jpt-4b-GGUF/jpt-4b.mmproj-bf16.gguf}"
ENGINE_PORT="${JPT_ENGINE_PORT:-8090}"   # raw llama-server weights/prefill
# 8082, NOT 8080: 8080 is reserved for other local work on this machine.
PORT="${JPT_PORT:-8084}"
NGL="${JPT_NGL:-99}"
CTX="${JPT_CTX:-16384}"
ENGINE_URL="http://127.0.0.1:${ENGINE_PORT}"
export JPT_ENGINE_URL="$ENGINE_URL" JPT_PORT="$PORT"

say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
die() { printf 'error: %s\n' "$*"; read -r -p "Press [Enter] to exit..."; exit 1; }

for f in "$GGUF" "$MMPROJ" "$LLAMA_BIN/llama-server"; do
  [ -e "$f" ] || die "not found: $f"
done

STARTED_ENGINE=0
STARTED_API=0
ENGINE_PID=""      # set -u: the reuse path leaves it unset,
                      # which aborted the script via `cleanup` and took the API with it
cleanup() {
  [ "$STARTED_API" = 1 ] && kill "$API_PID" 2>/dev/null
  [ "$STARTED_ENGINE" = 1 ] && kill "$ENGINE_PID" 2>/dev/null
}
trap cleanup EXIT

healthy() { curl -sf "$ENGINE_URL/health" >/dev/null 2>&1; }

verify_engine() {
  # `healthy` only proves SOMETHING is listening. NaviDC-OCR shares this host,
  # and reusing the wrong model silently turns every decision into OCR.
  curl -sf "$ENGINE_URL/v1/models" 2>/dev/null | grep -qi "jpt" || return 1
  return 0
}

if healthy && verify_engine; then
  say "reusing JPT-4B llama-server already on :$ENGINE_PORT"
elif healthy; then
  die "port $ENGINE_PORT is busy but is NOT a jpt-4b engine.
       Something else (NaviDC-OCR?) is bound there. Stop it, or set JPT_ENGINE_PORT=<free port>."
else
  say "starting llama-server on :$ENGINE_PORT (Vulkan, ngL=$NGL, ctx=$CTX)"
  "$LLAMA_BIN/llama-server" \
    -m "$GGUF" -mm "$MMPROJ" \
    --host 127.0.0.1 --port "$ENGINE_PORT" \
    -ngl "$NGL" -c "$CTX" --no-webui \
    >"/tmp/jpt-4b-server-$ENGINE_PORT.log" 2>&1 &
  ENGINE_PID=$!
  STARTED_ENGINE=1
  for _ in $(seq 1 120); do healthy && break; kill -0 "$ENGINE_PID" 2>/dev/null || break; sleep 1; done
  healthy || die "llama-server did not come up — see /tmp/jpt-4b-server-$ENGINE_PORT.log"
fi

if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  say "reusing System One API already on :$PORT"
else
  python3 "$APP_DIR/jpt_api.py" --port "$PORT" --engine "$ENGINE_URL" &
  API_PID=$!
  STARTED_API=1
  for _ in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 0.5; done
fi
say "System One API: http://127.0.0.1:$PORT/v1/systemone   (log: /tmp/jpt-4b-api-$PORT.log)"

if [ "$SERVE_ONLY" = 1 ]; then
  say "serving (--serve): Ctrl-C to stop"
  wait "$ENGINE_PID" 2>/dev/null || wait "$API_PID"
  exit 0
fi

python3 "$APP_DIR/jpt_chat.py"
status=$?

echo
read -r -p "Press [Enter] key to exit..."
exit $status