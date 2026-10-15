# Workstation Hardware & Local Inference Matrix

Hardware Topology, Dual GPU VRAM Budget, and Local Serving Endpoints.

---

## 1. Hardware Substrate Overview

- **CPU**: AMD Ryzen Processor (16 Threads: 4 Host Reserved, 12 Worker Dedicated)
- **Primary GPUs**: Dual AMD Radeon RX 9060 XT (32 GB Combined VRAM)
- **Acceleration Drivers**: ROCm (Primary FP4/FP8 compute) + Vulkan (DeskForge visual GUI grounding)
- **Local Proxy Gateway**: LiteLLM (`:4000`) & llama-swap (`:8000`)

---

## 2. Port-by-Port Local Services Registry

| Port | Service Daemon | Loaded Model / Engine | Purpose & Performance |
| :--- | :--- | :--- | :--- |
| **`:4000`** | `litellm` | LiteLLM Dynamic Proxy | OpenAI-compatible router with VRAM thresholding and cloud failovers |
| **`:8000`** | `llama-swap` | Model Hot-Swapper | Auto-loads/unloads GGUF models with dynamic concurrency sets |
| **`:8080`** | `llama-server` | **Qwen3.6-35B-A3B Uncensored Genesis** | Primary Workstation Coder (22 GB ROCMFP4, dual-GPU split `-ts 45/55`) |
| **`:8081`** | `audio.cpp` | **Nemotron 3.5 RNNT + Kokoro TTS** | Streaming STT (40 languages, word timestamps) & ultra-fast speech synthesis |
| **`:8082`** | `llama-server` | **bge-small-en-v1.5 (F16 GGUF)** | Dedicated 384-dimensional symmetric vector embeddings for local RAG |
| **`:8083`** | `llama-server` | **Imajev-4B ($T=1.305$)** | Calibrated decision model: discrete choice, ranking, and triage probabilities |
| **`:8084`** | `crispembed` | **CrispEmbed Suite (DBNet + PARSeq)**| Scene-text detection & line-level character recognition |
| **`:8085`** | `llama-server` | **LightOnOCR-3-1B** | **#1 Flagship Document & Video OCR** (~16,000 t/s prefill, ~330 t/s gen) |
| **`:8088`** | `llama-server` | **DeskForge-Qwen3.5-4B** (Vulkan) | Visual GUI grounding & pixel coordinate `(x, y)` extraction |
| **`:8090`** | `jpt-engine` | **JPT-4B Decision Engine** | System One decision router with multimodal projector |
| **`:9222`** | `podman` | **Chromium CDP** | Direct Chrome DevTools Protocol automated by Playwright |
| **`:3010`** | `podman` | **KasmVNC Desktop** | Live web desktop view for browser inspection |

---

## 3. Dual GPU VRAM Allocation Policy

To prevent Out-Of-Memory (OOM) crashes while running heavy local coder models, the workstation enforces a **22 GB Primary Floor + Dynamic Auxiliary Headroom** invariant:

```
[ GPU 0: 16 GB ]                       [ GPU 1: 16 GB ]
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  Genesis 35B Slice 1 (10 GB) │       │  Genesis 35B Slice 2 (12 GB) │
├──────────────────────────────┤       ├──────────────────────────────┤
│  LightOnOCR-3-1B (2.2 GB)    │       │  Imajev-4B / JPT-4B (2.5 GB) │
├──────────────────────────────┤       ├──────────────────────────────┤
│  audio.cpp Nemotron (1.8 GB) │       │  bge-small Embeddings (0.5GB)│
├──────────────────────────────┤       ├──────────────────────────────┤
│  VRAM Buffer (2.0 GB Headroom)       │  DeskForge Vulkan (1.0 GB)   │
└──────────────────────────────┘       └──────────────────────────────┘
```

1. **22 GB Primary Reserved**: Genesis 35B (`:8080`) remains permanently resident across both GPUs.
2. **Auxiliary Services Headroom**: Auxiliary models (OCR, Decision, STT, Embeddings) consume $\le$ 7.5 GB combined across remaining memory.
3. **Dynamic Swap via `:8000`**: If a heavy compile or vision task requires extra memory, `vram-rig-ctl swap` unloads inactive auxiliary instances automatically.

---

## 4. Workstation Health & Verification Command

To check the operational status of all local ports and services:
```bash
# Check all inference endpoints
vram-rig-ctl status

# Or check dual GPU VRAM utilization via ROCm
rocm-smi
```
