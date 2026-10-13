# Autonomous Workstation Model Directory & Rankings

Synthesized from local GPU inference configs, launchers, benchmarks, and agent conversation transcripts.

---

## 🏛️ Local Inference Ports

| Port | Model / Engine | Launcher | Primary Capabilities & Best Use |
|---|---|---|---|
| `:8080` | **Qwen3.6-35B-A3B Uncensored Genesis Final (Q4_0_ROCMFP4)** | `launchers/luffy_nothink.sh` / `luffy_thinking.sh` | **Flagship Workstation LLM** (22 GB, Vulkan dual-GPU `-ts 45/55`, replaced TTQ). High-throughput uncensored coding, reasoning, and agents. |
| `:8081` | **Nemotron 3.5 ASR + Kokoro TTS** | `audio.cpp` server | Real-time streaming speech-to-text (40 languages) + low-latency voice synthesis. |
| `:8082` | **NaviDC-OCR (Q8_0 / Q5_K_M)** | `launchers/navidc-ocr.sh` | Dense scanned academic papers and multi-page PDFs. |
| `:8083` | **Imajev-4B Decision Model** | `launchers/imajev-4b.sh` | Multimodal decision gating ($T=1.305$, vision + text via `imajev-4b-mmproj-f16.gguf`). |
| `:8084` | **CrispEmbed Scene Text OCR** | `launchers/crispembed-ocr.sh` | Real-world scene-text OCR, word/line crops (DBNet + PARSeq / TrOCR). |
| `:8085` | **LightOnOCR-3-1B** | `launchers/lighton-ocr.sh` | **#1 Flagship Video & Slide OCR** (~16k t/s prefill, ~330 t/s gen). |
| `:8086` | **Jina-Reranker-v2 Base** | `launchers/jina-reranker.sh` | Cross-encoder semantic search & RAG reranking. |
| `:8087` | **EmbeddingGemma-2** | `launchers/embeddinggemma-2.sh` | Text + Vision multimodal embeddings. |
| `:8088` | **DeskForge-Qwen3.5-4B** | `launchers/deskforge-qwen.sh` | Visual GUI grounding & desktop computer-use coordinates. |
| `:8090` | **JPT-4B Decision Engine** | `launchers/jpt-4b/start-jpt.sh` | **High-speed System One Decision Gating** with full multimodal vision support (`jpt-4b.mmproj-bf16.gguf`). |

---

## 🏆 Model Rankings by Task

### 1. Optical Character Recognition (OCR) & Document Understanding
1. **`LightOnOCR-3-1B` (and `LightOnOCR-3-4B`)** — **#1 Champion**
   - **Why**: Extreme inference throughput (~16,000 t/s prefill, ~330 t/s generation) on dual-GPU Vulkan setup. Flawless on video keyframe extraction, presentation slides, dense code blocks, and terminal recordings.
2. **`SmolDocling-256M` (`cstr/smoldocling-GGUF`)** — **#2 Document & Layout Specialist**
   - **Why**: Ultra-compact 256M model (SigLIP ViT + SmolLM2) running locally. Rather than flat text, generates structured **DocTags** XML markup capturing full page hierarchy, data tables, mathematical formulas, code blocks, and layout bounding boxes.
3. **`NaviDC-OCR` (`konradjr007` / `nandraj`)** — **#3 Dense Document Engine**
   - **Why**: Coordinate-free natural reading order transcription designed specifically for multi-column academic PDFs and scanned books.
4. **`CrispEmbed Suite` (`cstr/` GGUF models: DBNet-IC15 + TrOCR / PP-OCRv6 / PARSeq / GLM-OCR)** — **#4 Scene-Text & Crops**
   - **Why**: Ultra-lightweight CPU/GPU graph pipelines (DBNet detector at 13 MB, PP-OCRv6 at 5 MB, PARSeq at 25 MB). Ideal for line crops, scene photos, and noisy screenshots.
5. **Additional / Specialized Models in `/run/media/rodri/AI/models/`**:
   - `Xiaomi-OCR-0`: High accuracy alternative vision-language OCR.
   - `OvisOCR2` (`Abiray/OvisOCR2-GGUF`): High-fidelity ROCmFPX/BF16 VLM.
   - `Trocr-small-printed` (`cstr/`): Fast printed line OCR.

### 2. Calibrated Decision & Gating Models
1. **`JPT-4B` (`:8090`)** & **`Imajev-4B` (`:8083`)**
   - **Multimodal Support**: Both models feature active vision projectors (`jpt-4b.mmproj-bf16.gguf` and `imajev-4b-mmproj-f16.gguf`), enabling simultaneous visual and textual decision routing.
   - **Calibrated Scoring**: Used for classification, scoring, triage, and gated pipeline routing.
   - **Chaoliang Deprecation Note**: Chaoliang (`Jev-Style-Qwen3.5-2B`) was removed/deprecated. It lacks vision projector capabilities and benchmarks strictly worse than both `JPT-4B` and `Imajev-4B`.

### 3. Desktop GUI & Browser Grounding
- **`DeskForge-Qwen3.5-4B` (`:8088`)**: Primary visual grounding model for `hybrid-browser`. Translates screenshots into exact pixel interaction coordinates.
- **Alternative**: `DeskForge-Gemma4-E4B` (`mradermacher/`).

### 4. Speech-to-Text & Voice Synthesis
- **ASR**: `Nemotron-3.5-ASR-Streaming-0.6B` on `:8081` (RNNT architecture, 40 languages, streaming dictation).
- **TTS**: `Kokoro-82m` on `:8081` (instant local TTS) + `Omnivoice` / `Index-TTS-2.5` for multi-speaker synthesis.
- **Word Timestamps**: `Qwen3-Forced-Aligner-0.6B` (66× realtime forced alignment).
