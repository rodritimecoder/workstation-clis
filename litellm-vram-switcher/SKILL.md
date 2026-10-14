---
name: litellm-vram-switcher
description: >
  Manage local LLM/VLM/OCR/TTS servers across ports 8080-8090, inspect GPU VRAM usage,
  maintain the resident 22GB primary coder model with 10GB dynamic headroom, kill or swap
  models on demand, and operate the LiteLLM router gateway (port 4000) with automatic
  failover to OpenRouter Free and Gemini.
---

# LiteLLM & VRAM Port Switcher Skill (`litellm-vram-switcher`)

Use this skill to inspect GPU VRAM, monitor local servers listening on ports `8080–8090`, reclaim VRAM for specific workloads, manage model weights lifecycle, and route requests through the unified LiteLLM gateway on port `4000`.

## Architecture: Resident King + 10 GB Dynamic Headroom
Designed for 32 GB VRAM configurations (such as AMD dual RX 9060 XT or NVIDIA rigs):
- **Port `8080` (Pinned King, ~22 GB)**: High-capability coder model (`qwen-coder-35b-q4_k_m`) remains resident in VRAM 24/7 for 0ms cold-start latency.
- **Ports `8082–8083` (Dynamic Headroom, ~10 GB)**: Auxiliary models (`jev-4b` 3.5 GB classifier, `glm-ocr` 4.0 GB) run **simultaneously alongside the coder** without triggering evictions.
- **Heavy Task Fallback**: If a batch of tasks demands >10 GB headroom, the controller gracefully pauses port 8080, runs the heavy workload, and reboots port 8080 when complete.
- **Port `4000` (LiteLLM Proxy)**: Single unified OpenAI-compatible gateway (`http://localhost:4000/v1`).
  - Routes to local ports `8080–8090` first.
  - Automatically fails over to `openrouter/free` or `gemini-2.5-flash` if a local port is offline or busy.

## Commands

### 1. Check GPU VRAM & Active Ports (`8080–8090`)
```bash
vram-rig-ctl status
```

### 2. Free VRAM by Killing Specific Port(s) or Evicting All
Kill a specific port (e.g. `8081`):
```bash
vram-rig-ctl kill --port 8081
```
Evict all non-pinned servers across `8080–8090`:
```bash
vram-rig-ctl evict-all
```

### 3. Smart Swap: Start a Model on `8080–8090`
Checks required VRAM from `port_registry.json`. If headroom permits, starts immediately without killing the primary coder. If headroom is exceeded, frees non-pinned ports first:
```bash
vram-rig-ctl swap --port 8082
```

### 4. Start / Restart LiteLLM Gateway (Port `4000`)
```bash
vram-rig-ctl gateway-up
```
