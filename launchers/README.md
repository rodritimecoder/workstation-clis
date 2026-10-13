# Launcher Scripts & Benchmarks (`/run/media/rodri/AI/sh`)

Collection of launcher shell scripts for workstation inference servers, benchmarks, and voice utilities.

---

## Server Launchers

| Script | Server / Backend | Port | Description |
|---|---|---|---|
| **`luffy_nothink.sh`** / **`luffy_thinking.sh`** | `llama-server` (Vulkan) | `8080` | **Primary Workstation LLM**: Qwen3.6-35B-A3B Uncensored Genesis Final (Q4_0_ROCMFP4, dual-GPU `-ts 45/55`) |
| **`lighton-ocr.sh`** | `llama-server` (Vulkan) | `8085` | **#1 Flagship OCR (Video, Slide & Document)**: LightOnOCR-3-1B (~16k t/s prefill, ~330 t/s gen) |
| **`imajev-4b.sh`** | `llama-server` (Vulkan) | `8083` | Launches Imajev-4B with vision mmproj for calibrated multimodal decisions |
| **`crispembed-ocr.sh`** | `crispembed-server` (Vulkan/CPU) | `8084` | Launches CrispEmbed Scene Text OCR (DBNet + PARSeq / TrOCR) |
| **`navidc-ocr.sh`** | `llama-server` (Vulkan) | `8082` | Legacy document OCR with patched `llama-server` |
| **`jina-reranker.sh`** | `llama-server` (Vulkan) | `8086` | Launches Jina-Reranker-v2 Base Multilingual for RAG cross-encoder reranking |
| **`embeddinggemma-2.sh`** | `llama-server` (Unsloth Vulkan) | `8087` | Launches EmbeddingGemma-2 (text + vision mmproj) for multimodal embeddings |
| **`deskforge-qwen.sh`** | `llama-server` (Vulkan) | `8088` | Launches DeskForge-Qwen3.5-4B for computer-use GUI grounding |
| **`jpt-4b/`** | `jpt-engine` | `8090` | JPT-4B System One decision server with multimodal vision projector (`jpt-4b.mmproj-bf16.gguf`) |

---

## Audio & Voice Scripts

| Script | Purpose |
|---|---|
| **`mic-asr.sh`** | Real-time microphone dictation using GStreamer + audio.cpp ASR endpoint |
| **`mic-tts.sh`** | Voice synthesis playback using Kokoro / Kitten |
| **`mic-tts.py`** | Python voice pipeline integration |
| **`make-voice-ref.sh`** | Helper to generate reference audio clips for voice cloning |

---

## Model Launchers & Benchmarks

| Script | Purpose |
|---|---|
| **`luffy_thinking.sh`** / **`luffy_nothink.sh`** | Run Luffy Qwen 35B models with / without reasoning tokens |
| **`gemma_nothink.sh`** | Run Gemma4 26B without thinking blocks |
| **`bench-luffy-q4-rocmfp4.sh`** | Benchmarks ROCm FP4 performance on dual RX 9060 XT |
| **`bench-luffy-q4km.sh`** | Benchmarks Q4_K_M on dual RX 9060 XT |
| **`bench-gemma-vulkan.sh`** / **`bench-gemma-rocm.sh`** | Benchmarks comparing Vulkan vs ROCm on Gemma models |

---

## Further Documentation
- [Workstation Models & Rankings Guide](../docs/models_and_services.md)
- [CSTR & CrispEmbed Model Suite](../docs/cstr_models.md)
