#!/usr/bin/env bash
# run-audiocpp — start the audio.cpp server (Vulkan, port 8081).
#
# Uses server.json in this directory, which registers all 14 GGUFs from
# /run/media/rodri/AI/models/audio-cpp/audio.cpp-gguf. Models load lazily on
# first request, so startup is fast; max_loaded_models keeps 3 warm.
#
# Env knobs:
#   PORT=8081        override the port from server.json
#   BACKEND=vulkan   cpu | vulkan | cuda | metal
#   UI=1             also open the WebUI (default: server only, ui:true in config)

set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${APP_DIR}/server.json"
SERVER="${APP_DIR}/audiocpp_server"
PORT="${PORT:-8081}"

[ -x "$SERVER" ] || { echo "not executable: $SERVER"; exit 1; }
[ -f "$CONFIG" ] || { echo "missing config: $CONFIG"; exit 1; }

if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "audio.cpp already answering on ${PORT} — nothing to do."
  echo "stop it first, or use PORT=8082"
  exit 0
fi

echo "audio.cpp 0.9.2 — Vulkan backend, port ${PORT}"
echo "config: $CONFIG"
echo "Ctrl-C to stop."
echo

exec "$SERVER" --config "$CONFIG" "$@"