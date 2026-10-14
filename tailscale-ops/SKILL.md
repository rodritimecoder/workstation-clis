---
name: tailscale-ops
description: >
  Runtime Tailscale network operations for discovering online homelab/desktop nodes,
  exposing local web servers or LLM ports over private HTTPS (tailscale serve),
  opening temporary public webhook endpoints (tailscale funnel), and transferring
  artifacts across devices (tailscale file cp).
---

# Tailscale Operations Skill (`tailscale-ops`)

Use this skill whenever you need to check if a remote compute/GPU node is online, expose a local dev server or LLM endpoint safely, receive external webhooks, or send files to another machine on the tailnet.

## Commands

### 1. Discover Online Nodes & Tailscale IPs
Check which machines on the tailnet are currently awake and get their `100.x.y.z` IPv4 addresses and DNS names:
```bash
tailscale-ops peers
```

### 2. Check if a Specific Host/Port is Reachable
Before routing heavy jobs to a remote GPU host, verify both the node and target port (e.g., `8080` or `4000`) respond:
```bash
tailscale-ops check-port <hostname-or-ip> <port>
```

### 3. Expose a Local Port Privately to the Tailnet (`serve`)
Expose a local dev server or LiteLLM gateway (`localhost:3000` or `localhost:4000`) with automatic HTTPS strictly inside the tailnet:
```bash
tailscale-ops serve-on 4000
```

### 4. Expose a Local Port Publicly for Webhooks (`funnel`)
Open a temporary public HTTPS tunnel (ports 443, 8443, or 10000) so external services (GitHub Actions, PostHog, webhooks) can reach a local listener:
```bash
tailscale-ops funnel-on 8080
```

### 5. Tear Down All Active Serve / Funnel Tunnels
Always clean up temporary tunnels once verification or webhook testing finishes:
```bash
tailscale-ops reset-tunnels
```

### 6. Send Files to Another Tailnet Device (`file cp`)
Beam build artifacts, logs, or screenshots directly to another online node without configuring SCP/SSH keys:
```bash
tailscale-ops send-file ./artifact.zip <target-hostname>:
```
