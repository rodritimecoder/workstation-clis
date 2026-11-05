# Model Server Launchers — Agent Invariants (`/run/media/rodri/AI/sh/AGENTS.md`)

Governs all AI assistants managing, starting, stopping, or modifying local model launchers on this machine.

---

## 🛡️ Core Rules & Invariants

1. **Single Source of Truth:**
   `/run/media/rodri/AI/sh` is the authoritative source for all launcher scripts.
   - The copies at `skills/launchers/` and `workstation-clis/launchers/` are derived.
   - Edit scripts HERE, then run `sync-skills` to propagate.
   - Run `python3 /home/rodri/src/my-agent-skills/hardware/model-layer/scripts/ports.py drift` before editing to check for divergence.

2. **Trust `omnicli status` Over Open Ports:**
   `tailscale serve` holds tailnet listeners for these ports. A listening socket proves the proxy is up, NOT that the model backend is live.
   - Check service health via:
     ```bash
     omnicli status
     ```
   - Or test loopback directly: `curl -s http://127.0.0.1:<PORT>/health`.

3. **Dual-GPU Allocation Rules (Dual Radeon RX 9060 XT):**
   - Port `:8080` (Primary 35B Generative LLM): Vulkan dual-GPU split.
   - Port `:8081` (`audiocpp`): Native Vulkan/ROCm speech engine (ASR/TTS/align).
   - Port `:8083` (`h2o-lightning-4b`): Dedicated decision slot; do not run open-ended generative chat through `:8083`.
   - Never launch overlapping models on the same port or exceed VRAM headroom without running `vram-rig-ctl`.

4. **Background Execution Discipline:**
   - Server scripts run as background daemons (`nohup` / `&` or systemd).
   - Never run a blocking launcher script directly in a synchronous conversation turn.
