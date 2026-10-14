#!/usr/bin/env bash
# ts_ops.sh — Runtime Tailscale Network Operations for AI Agents

set -euo pipefail

CMD="${1:-peers}"
shift || true

# Helper: Check if tailscale CLI is available
check_tailscale() {
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "❌ Error: tailscale CLI not found in PATH." >&2
    echo "   Ensure Tailscale is installed and running." >&2
    exit 1
  fi
}

case "$CMD" in
  peers)
    check_tailscale
    tailscale status --json | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    peers = []
    # Include self
    self_node = data.get("Self", {})
    if self_node:
        peers.append({
            "hostname": self_node.get("HostName"),
            "dns_name": self_node.get("DNSName", "").rstrip("."),
            "tailscale_ip": (self_node.get("TailscaleIPs") or [""])[0],
            "os": self_node.get("OS"),
            "online": True,
            "self": True
        })
    # Include other peers
    for p in (data.get("Peer") or {}).values():
        if p.get("Online", False):
            peers.append({
                "hostname": p.get("HostName"),
                "dns_name": p.get("DNSName", "").rstrip("."),
                "tailscale_ip": (p.get("TailscaleIPs") or [""])[0],
                "os": p.get("OS"),
                "online": True,
                "self": False
            })
    print(json.dumps(peers, indent=2))
except Exception as e:
    sys.stderr.write(f"Error parsing tailscale status: {e}\n")
    sys.exit(1)
'
    ;;

  check-port)
    HOST="${1:?Target hostname or Tailscale IP required}"
    PORT="${2:?Target port required}"
    
    python3 -c "
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.5)
try:
    s.connect((host, port))
    s.close()
    print(f'✅ ONLINE: {host}:{port} is reachable.')
    sys.exit(0)
except Exception as e:
    print(f'❌ OFFLINE: {host}:{port} is unreachable ({e}).')
    sys.exit(1)
" "$HOST" "$PORT"
    ;;

  serve-on)
    check_tailscale
    PORT="${1:?Local port required}"
    echo "🔒 Exposing localhost:$PORT over private Tailscale HTTPS..."
    tailscale serve --bg "$PORT"
    tailscale serve status
    ;;

  funnel-on)
    check_tailscale
    PORT="${1:?Local port required}"
    echo "🌐 Opening public Tailscale Funnel on port 443 -> localhost:$PORT..."
    tailscale funnel --bg --https=443 "http://127.0.0.1:${PORT}"
    tailscale funnel status
    ;;

  reset-tunnels)
    check_tailscale
    echo "🧹 Resetting all active Tailscale serve and funnel tunnels..."
    tailscale serve reset 2>/dev/null || true
    tailscale funnel reset 2>/dev/null || true
    echo "✅ All Tailscale serve and funnel configurations cleared."
    ;;

  send-file)
    check_tailscale
    FILE_PATH="${1:?File path required}"
    TARGET="${2:?Target node required (e.g. gaming-pc:)}"
    [[ "$TARGET" != *: ]] && TARGET="${TARGET}:"
    tailscale file cp "$FILE_PATH" "$TARGET"
    echo "✅ Sent ${FILE_PATH} to ${TARGET}"
    ;;

  *)
    echo "Usage: $0 {peers|check-port|serve-on|funnel-on|reset-tunnels|send-file}" >&2
    echo "  peers"
    echo "  check-port <hostname-or-ip> <port>"
    echo "  serve-on <port>"
    echo "  funnel-on <port>"
    echo "  reset-tunnels"
    echo "  send-file <file-path> <target-node:>"
    exit 1
    ;;
esac
