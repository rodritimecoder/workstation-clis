---
name: litellm-vram-switcher
description: >
  Manage local LLM/VLM/OCR/TTS servers with llama-swap (port 8000) and LiteLLM (port 4000),
  inspect dual GPU VRAM usage, maintain the 22GB primary coder model with dynamic auxiliary
  headroom, and automatically failover to OpenRouter Free and Gemini.
---

# LiteLLM & llama-swap VRAM Controller (`litellm-vram-switcher`)

Use this skill to inspect GPU VRAM, operate the automated model-swapping reverse proxy (**`llama-swap` on port `8000`**), manage direct ports `8080–8090`, and route requests through the unified **LiteLLM gateway on port `4000`**.

## Architecture: Resident King + 10 GB Dynamic Headroom
Engineered for Dual AMD Radeon RX 9060 XT (32 GB total VRAM):
- **Port `8000` (`llama-swap`)**: Native Go model-swapping proxy with automated VRAM solver matrix:
  - **`qwen3.6-35b` (Pinned King, ~22 GB)**: Q4_0 ROCMFP4 uncensored model split across both GPUs (`-ts 45/55`).
  - **`vllm-d3-mini` (Premier Decision, ~3.7 GB)**: Native `/v1/systemone` decision model (5B, Q4_K_M) with multimodal projector; ~70 ms, zero generated tokens. OneJev1.5-4B remains the calibrated fallback on `:8089`.
  - **`lighton-ocr` (Auxiliary Vision OCR, ~1.5 GB)**: Flagship 16k t/s slide/doc OCR. Runs concurrently alongside Qwen3.6 and Imajev!
  - **`deskforge-4b` (GUI Grounding, ~3.5 GB)**: Desktop computer-use coordinate extraction agent.
  - **`gemma4-26b` (Heavy General Model, ~18 GB)**: Automatically evicts Qwen3.6 when called, and swaps Qwen3.6 back when needed.
- **Port `4000` (`LiteLLM Gateway`)**: Unified OpenAI-compatible API (`http://localhost:4000/v1`):
  - Routes local models to `llama-swap` on port `8000`.
  - Automatically fails over to `openrouter/free` (Nemotron 70B Free) or `gemini/gemini-2.5-flash` if local inference is offline or busy.

---

## 🚀 Commands

### 1. Check VRAM & All Model Servers
```bash
vram-rig-ctl status
```

### 2. Start / Stop `llama-swap` (Port `8000`)
```bash
# Start llama-swap daemon on port 8000 with watch-config
vram-rig-ctl llama-swap-up

# Check running models and configured models
vram-rig-ctl llama-swap-status

# Stop llama-swap and unload active models
vram-rig-ctl llama-swap-down
```

### 3. Start / Stop `LiteLLM` Gateway (Port `4000`)
```bash
# Start LiteLLM proxy on port 4000
vram-rig-ctl gateway-up

# Stop LiteLLM proxy
vram-rig-ctl gateway-down
```

### 4. Direct Port Controls (`8080–8090`)
```bash
# Kill a specific port listener (e.g. 8081)
vram-rig-ctl kill --port 8081

# Evict all non-pinned auxiliary ports to free headroom
vram-rig-ctl evict-all

# Manual single-port swap
vram-rig-ctl swap --port 8083
```
