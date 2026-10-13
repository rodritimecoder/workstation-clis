#!/usr/bin/env bash
# hybrid-browser-service.sh — Service manager for Hybrid DeskForge Browser
set -euo pipefail

CONTAINER_NAME="hybrid-browser"
IMAGE="lscr.io/linuxserver/chromium:latest"
PROFILE_DIR="${HOME}/.local/share/hybrid-browser-profile"
VNC_PORT="3010"
CDP_PORT="9222"
DESKFORGE_SH="/run/media/rodri/AI/sh/deskforge-qwen.sh"

action="${1:-status}"

start_podman() {
  mkdir -p "$PROFILE_DIR"
  # Ensure enterprise policy directory exists with uBlock Origin Lite policy
  podman unshare mkdir -p "${PROFILE_DIR}/policies/managed"
  podman unshare sh -c 'cat << "EOF" > '"${PROFILE_DIR}"'/policies/managed/extensions.json
{
  "ExtensionInstallForcelist": [
    "ddkjiahejlhfcafbddmgiahcphecmpfh;https://clients2.google.com/service/update2/crx"
  ]
}
EOF'
  # Ensure labwc autostart includes internal forwarder from 0.0.0.0:9222 -> 127.0.0.1:9223
  podman unshare mkdir -p "${PROFILE_DIR}/.config/labwc"
  podman unshare sh -c 'cat << "EOF" > '"${PROFILE_DIR}"'/.config/labwc/autostart
#!/bin/bash
BIN=/usr/bin/chromium
${BIN} \
  --no-sandbox \
  --password-store=basic \
  --simulate-outdated-no-au="Tue, 31 Dec 2099 23:59:59 GMT" \
  --start-maximized \
  --test-type \
  --user-data-dir \
  --ozone-platform=wayland \
  --remote-debugging-port=9223 &

# Forward 0.0.0.0:9222 -> 127.0.0.1:9223
python3 -c "
import socket, threading
def forward(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data: break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        src.close()
        dst.close()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((\"0.0.0.0\", 9222))
s.listen(100)
while True:
    client, _ = s.accept()
    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        remote.connect((\"127.0.0.1\", 9223))
        threading.Thread(target=forward, args=(client, remote), daemon=True).start()
        threading.Thread(target=forward, args=(remote, client), daemon=True).start()
    except Exception:
        client.close()
"
EOF
chmod +x '"${PROFILE_DIR}"'/.config/labwc/autostart'

  if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Podman browser container is already running."
  elif podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting existing Podman browser container..."
    podman start "$CONTAINER_NAME"
  else
    echo "Creating and launching Podman browser container ($IMAGE)..."
    podman run -d \
      --name "$CONTAINER_NAME" \
      --dns 1.1.1.1 --dns 8.8.8.8 \
      -p "${VNC_PORT}:3000" \
      -p "${CDP_PORT}:9222" \
      -v "${PROFILE_DIR}:/config:Z" \
      -v "${PROFILE_DIR}/policies:/etc/chromium/policies:ro,Z" \
      --shm-size="2gb" \
      "$IMAGE"
  fi
}

start_deskforge() {
  if curl -fsS -m 2 http://127.0.0.1:8088/health >/dev/null 2>&1; then
    echo "DeskForge-Qwen3.5-4B server is already healthy on :8088."
  else
    echo "Launching DeskForge-Qwen3.5-4B server via $DESKFORGE_SH in background..."
    nohup "$DESKFORGE_SH" > /tmp/deskforge_server.log 2>&1 &
    
    echo "Waiting for DeskForge to warm up on port 8088..."
    for i in {1..30}; do
      if curl -fsS -m 1 http://127.0.0.1:8088/health >/dev/null 2>&1; then
        echo "DeskForge server is ready!"
        return 0
      fi
      sleep 1
    done
    echo "Warning: DeskForge took longer than 30s to report healthy. Check /tmp/deskforge_server.log"
  fi
}

stop_all() {
  echo "Stopping Podman browser container..."
  podman stop "$CONTAINER_NAME" 2>/dev/null || true
  echo "Stopping DeskForge server (if running)..."
  pkill -f "DeskForge-Qwen3.5-4B" 2>/dev/null || true
}

open_gui() {
  echo "Opening live browser desktop GUI..."
  if which chromium >/dev/null 2>&1; then
    chromium --app="http://127.0.0.1:${VNC_PORT}" --window-size=1280,800 >/dev/null 2>&1 &
  elif which google-chrome >/dev/null 2>&1; then
    google-chrome --app="http://127.0.0.1:${VNC_PORT}" --window-size=1280,800 >/dev/null 2>&1 &
  else
    xdg-open "http://127.0.0.1:${VNC_PORT}" >/dev/null 2>&1 &
  fi
}

case "$action" in
  start)
    start_podman
    start_deskforge
    echo
    echo "=== Hybrid Browser Stack Online ==="
    echo "Live Interactive GUI (KasmVNC): http://127.0.0.1:${VNC_PORT}"
    echo "DevTools CDP Endpoint:         http://127.0.0.1:${CDP_PORT}"
    echo "DeskForge Grounding API:       http://127.0.0.1:8088/v1/chat/completions"
    ;;
  gui)
    open_gui
    ;;
  stop)
    stop_all
    ;;
  status)
    echo "Container status:"
    podman ps -a --filter name="$CONTAINER_NAME"
    echo
    echo "DeskForge health check:"
    curl -fsS -m 2 http://127.0.0.1:8088/health 2>/dev/null && echo " (OK)" || echo " (Offline)"
    ;;
  *)
    echo "Usage: $0 {start|gui|stop|status}"
    exit 1
    ;;
esac
