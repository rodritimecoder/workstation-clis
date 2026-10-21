# Launcher Scripts & Benchmarks (`/run/media/rodri/AI/sh`)

Collection of launcher shell scripts for workstation inference servers, benchmarks, and voice utilities.

**This directory is the single source of truth for launchers.** The copies at
`skills/launchers/` and `workstation-clis/launchers/` are generated from here by
`skills/sync_skills.sh`; edit this directory and re-run the sync, never the
copies. `python3 skills/ports.py drift` reports any divergence.

---

## Server Launchers

<!-- ports:begin -->
| Port | Slot | Cardinality | Default model | Launcher | Role |
|---|---|---|---|---|---|
| `:8080` | `llm` | many (7) | Qwen3.6-35B-A3B-Uncensored-Genesis-Final | `luffy_nothink.sh` | Primary generative LLM — chat, code, long-form writing, prose projection |
| `:8081` | `audio` | many (3) | nemotron-asr | `run-audiocpp.sh` | Speech-to-text, text-to-speech, forced alignment, voice cloning |
| `:8083` | `decision` | one-of-many (3) | StartLux-Decision-v1.1-4B-Instant | `startlux-decision.sh` | The decision engine slot - bool / choice / score primitives |
| `:8082` | `decision-engine` | single (1) | StartLux-Decision-v1.1-4B-Instant | `startlux-decision.sh` | Internal engine of the :8083 decision slot - prompts in one micro-batch, not a client-facing API |
| `:8084` | `ocr-crispembed` | single (1) | CrispEmbed (PP-OCRv6 small: DB++ det + CTC rec) | `crispembed-ocr.sh` | Scene text — 2D bounding boxes and structured markdown |
| `:8085` | `ocr-lighton` | single (1) | LightOnOCR-3-1B | `lighton-ocr.sh` | Documents, PDFs and slides — fast prefill, high-throughput markdown |
| `:8086` | `reranker` | single (1) | jina-reranker-v2-base-multilingual | `jina-reranker.sh` | Cross-encoder reranking for RAG |
| `:8087` | `embed` | one-of-many (2) | bge-small-en-v1.5 | `bge-small.sh` | Vector embeddings for RAG and semantic caching |

| Port | Infra | Service | Role |
|---|---|---|---|
| `:4000` | `litellm` | LiteLLM gateway | OpenAI-compatible failover gateway; routes to llama-swap |
| `:8000` | `llama-swap` | llama-swap | Model multiplexer behind LiteLLM; swaps models in/out of VRAM |
| `:3010` | `kasmvnc` | KasmVNC (podman) | Live interactive web desktop for browser inspection |
| `:9222` | `cdp` | Chromium DevTools | CDP endpoint used by fast-cdp and Playwright |
| `:9223` | `cdp-internal` | labwc forwarder | Container-internal forwarder 0.0.0.0:9222 -> 127.0.0.1:9223 |
<!-- ports:end -->

---

## Audio & Voice Scripts

| Script | Purpose |
|---|---|
| **`mic-asr.sh`** | Real-time microphone dictation using GStreamer + the audio.cpp ASR endpoint on `:8081` |
| **`mic-tts.sh`** | Voice synthesis playback using Kokoro / Kitten |
| **`mic-tts.py`** | Python voice pipeline integration |
| **`make-voice-ref.sh`** | Helper to generate reference audio clips for voice cloning |

---

## Model Launchers & Benchmarks

| Script | Purpose |
|---|---|
| **`luffy_thinking.sh`** | Qwen3.6-35B Genesis with reasoning tokens enabled |
| **`luffy_nothink.sh`** | Same model with `enable_thinking=false` (the default LLM, `:8080`) |
| **`ttq_server.sh`** | TTQ / MTP speculative-decoding experiment on `:8080` |
| **`gemma_nothink.sh`** | Gemma4 26B without thinking blocks |
| **`gemma_nothink_official.sh`**, **`gemma_rocm_split.sh`**, **`gemma_vulkan_layer.sh`** | Gemma4 26B with different backend and layer-split strategies |
| **`bge-small.sh`** | bge-small-en-v1.5 (384d) — the default embedding candidate on `:8087` |
| **`embeddinggemma-2.sh`** | EmbeddingGemma-2 (768d, multimodal) — the alternate embedding candidate on `:8087` |
| **`vllm.sh`** | Interactive vLLM ROCm container (a tool, not a service slot) |
| **`bench-ttq-iq4nl.sh`** | Vulkan pp2048/tg128 benchmark for Qwen3.6-35B TTQ IQ4_NL |
| **`bench-luffy-q4km.sh`** / **`bench-luffy-q4-rocmfp4.sh`** | Benchmarks comparing Q4_K_M vs ROCm FP4 on RX 9060 XT |
| **`bench-gemma-vulkan.sh`** / **`bench-gemma-rocm.sh`** | Benchmarks comparing Vulkan vs ROCm on Gemma models |

`archived/` holds retired launchers kept for reference: the `JPT-4B`,
`OneJev1.5-4B` and `Imajev-4B` decision models, and `Jev-Style-Qwen3.5-2B`.
The decision engine is `vllm-d3-mini` on `:8083` with no fallback.

---

## Further Documentation

- [Port manifest and slot map](../skills/ports.json) — the source of truth for every port
- [Workstation Models & Rankings Guide](../skills/docs/models_and_services.md)
- [Hardware & Local Inference Matrix](../skills/docs/hardware-and-inference-matrix.md)
