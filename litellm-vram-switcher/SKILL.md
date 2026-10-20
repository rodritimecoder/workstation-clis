---
name: litellm-vram-switcher

description: >
  Manage the local LLM, VLM, OCR and TTS servers on dual-GPU hardware.
  Inspect VRAM, swap models in and out on port 8000, run the LiteLLM gateway
  on port 4000, and free headroom on ports 8080-8088.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires Dual AMD Radeon RX 9060 XT GPUs with Vulkan, the llama.cpp binaries, and the LiteLLM gateway on :4000."
metadata:
  author: "rodri"
allowed-tools: "Bash(vram-rig-ctl:*) Bash(python3:*) Read"
---

# LiteLLM & llama-swap VRAM Controller (`litellm-vram-switcher`)

Operates the local inference stack: a Go model-swapping proxy on port 8000
and an OpenAI-compatible LiteLLM gateway on port 4000, over dual RX 9060 XT
cards with 32 GB of VRAM between them.

---

## 🏛️ The Resident King

One model is pinned and everything else is dynamic. The King holds the VRAM;
the auxiliary models are evicted and restored on demand.

| Model | VRAM | Role |
| :--- | :--- | :--- |
| `qwen3.6-35b` | ~22 GB | **Pinned King** — Q4_0 ROCMFP4, split across both GPUs (`-ts 45/55`) |
| `gemma4-26b` | ~18 GB | Heavy general model; evicts the King when called, and swaps it back when done |
| `vllm-d3-mini` | ~3.7 GB | **The** decision model: native `/v1/systemone` on `:8083`, ~70 ms, zero generated tokens, vision via `mmproj` |
| `deskforge-4b` | ~3.5 GB | Desktop computer-use coordinate extraction |
| `lighton-ocr` | ~1.5 GB | Flagship 16k t/s slide and document OCR; runs concurrently alongside the King |

The **LiteLLM gateway** on `:4000` routes to `llama-swap` on `:8000`, and
fails over to `openrouter/free` or `gemini/gemini-2.5-flash` when local
inference is offline or busy.

---

## 🛠️ CLI Quickstart

```bash
# 1. Check VRAM and every model server
vram-rig-ctl status

# 2. Start, inspect, and stop llama-swap (port 8000)
vram-rig-ctl llama-swap-up
vram-rig-ctl llama-swap-status
vram-rig-ctl llama-swap-down

# 3. Start and stop the LiteLLM gateway (port 4000)
vram-rig-ctl gateway-up
vram-rig-ctl gateway-down

# 4. Kill a specific port listener
vram-rig-ctl kill --port 8081

# 5. Evict every non-pinned auxiliary port to free headroom
vram-rig-ctl evict-all

# 6. Manually swap a single port
vram-rig-ctl swap --port 8083
```
