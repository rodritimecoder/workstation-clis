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

  serve-mesh)
    check_tailscale
    DNS_NAME=$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin).get("Self", {}).get("DNSName", "").rstrip("."))')
    echo "⚡ Exposing Workstation AI Inference Matrix over Private Tailscale HTTPS (${DNS_NAME})..."
    
    SERVICES=(
      "4000:LiteLLM Dynamic Gateway"
      "8000:llama-swap Controller"
      "8080:Genesis 35B Primary LLM"
      "8081:audio.cpp Nemotron ASR & Kokoro TTS"
      "8082:bge-small Embeddings"
      "8083:Imajev-4B Decision Gating"
      "8084:CrispEmbed Scene-Text OCR"
      "8085:LightOnOCR Flagship Document OCR"
      "8088:DeskForge Visual GUI Grounding"
      "8090:JPT-4B Decision Engine"
      "3010:KasmVNC Browser Web Desktop"
    )

    for item in "${SERVICES[@]}"; do
      PORT="${item%%:*}"
      NAME="${item##*:}"
      echo "  • Serving $NAME on :$PORT..."
      tailscale serve --bg --https "$PORT" "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
    done

    echo ""
    echo "✅ Workstation Inference Mesh Online across Tailnet:"
    printf "  %-38s %s\n" "SERVICE" "TAILSCALE HTTPS URL"
    echo "  ────────────────────────────────────────────────────────────────────────────────"
    for item in "${SERVICES[@]}"; do
      PORT="${item%%:*}"
      NAME="${item##*:}"
      printf "  %-38s https://%s:%s\n" "$NAME" "$DNS_NAME" "$PORT"
    done
    ;;

  mesh-status)
    check_tailscale
    DNS_NAME=$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin).get("Self", {}).get("DNSName", "").rstrip("."))')
    echo "📊 Workstation Tailscale Mesh Status (${DNS_NAME}):"
    tailscale serve status
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
    echo "Usage: $0 {peers|check-port|serve-mesh|mesh-status|serve-on|funnel-on|reset-tunnels|send-file}" >&2
    echo "  peers"
    echo "  check-port <hostname-or-ip> <port>"
    echo "  serve-mesh             # Expose all 11 workstation inference services over Tailscale HTTPS"
    echo "  mesh-status            # View active Tailscale serve configurations"
    echo "  serve-on <port>        # Expose single port privately on tailnet"
    echo "  funnel-on <port>       # Expose single port publicly via funnel"
    echo "  reset-tunnels          # Tear down all serve and funnel tunnels"
    echo "  send-file <file-path> <target-node:>"
    exit 1
    ;;
esac
