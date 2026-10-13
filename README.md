# workstation-clis

[![Public Repository](https://img.shields.io/badge/Repository-Public-green.svg)](https://github.com/rodritimecoder/workstation-clis)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tools: 8 CLIs](https://img.shields.io/badge/Tools-8%20CLIs-blue.svg)](#-included-clis--tools)
[![Hardware: Dual RX 9060 XT](https://img.shields.io/badge/Hardware-Dual%20RX%209060%20XT-purple.svg)](#-workstation-architecture--ports)

> High-performance local CLI utilities, automation agents, and multimodal inference pipelines designed for autonomous AI workstations.

---

## 🏛️ Workstation Architecture & Ports

This suite is engineered for a local **dual AMD Radeon RX 9060 XT** setup running ROCm and Vulkan-accelerated backends with zero cloud dependencies:

| Port | Model / Backend | Primary Capabilities |
|---|---|---|
| `:8080` | **Qwen3.6-35B-A3B Uncensored Genesis** | Primary Workstation LLM (22 GB ROCMFP4, dual-GPU `-ts 45/55`) |
| `:8081` | **audio.cpp (Nemotron 3.5 + Kokoro)** | Streaming speech-to-text (40 languages) & fast text-to-speech |
| `:8085` | **LightOnOCR-3-1B** | **#1 Flagship Video & Slide OCR** (~16k t/s prefill, ~330 t/s gen) |
| `:8083` | **Imajev-4B ($T=1.305$)** | Calibrated multimodal decision gating (vision + text) |
| `:8084` | **CrispEmbed Suite** | Ultra-compact scene-text detection & line recognition (DBNet + PARSeq) |
| `:8086` | **Jina-Reranker-v2 Base** | Cross-encoder semantic search & RAG reranking |
| `:8087` | **EmbeddingGemma-2** | Text + Vision multimodal embeddings |
| `:8088` | **DeskForge-Qwen3.5-4B** | Visual GUI grounding & computer-use coordinate extraction |
| `:8090` | **JPT-4B Decision Engine** | System One decision gating with multimodal vision projector |

---

## 📦 Included CLIs & Tools

| Tool Directory | Identifier | Core Capabilities |
| :--- | :--- | :--- |
| [`ocr-cli`](ocr-cli/) | `ocr-cli` | Multi-model local OCR engine uniting LightOnOCR-3-1B (#1 flagship), SmolDocling, and CrispEmbed. |
| [`hybrid-browser`](hybrid-browser/) | `hybrid-browser` | Tiered browser automation agent using Podman Chromium, CDP, and DeskForge-Qwen3.5-4B visual grounding. |
| [`video-miner`](video-miner/) | `video-miner` | 6-stage ICM video mining orchestrator combining Nemotron ASR, Imajev visual gating, and LightOnOCR code extraction. |
| [`audiocpp-asr`](audiocpp-asr/) | `audiocpp-asr` | Local speech-to-text with Nemotron-3.5 streaming RNNT, hotword prompting, and live mic dictation. |
| [`jev-cli`](jev-cli/) | `jev-cli` | Calibrated decision model CLI querying Imajev-4B and JPT-4B for probabilities, classifications, and gating. |
| [`markitdown-cli`](markitdown-cli/) | `markitdown-cli` | Universal document converter to Markdown (PDF, DOCX, XLSX, PPTX, CSV, HTML, Audio). |
| [`canvas-cli`](canvas-cli/) | `canvas-cli` | Canvas LMS CLI fetching courses, assignments, grades, announcements, modules, and files. |
| [`zoom-recorder`](zoom-recorder/) | `zoom-recorder` | Cloud Zoom recording downloader (transcripts, audio, and visual keyframe slides). |

---

## 🚀 Tool Highlights

### 1. `ocr-cli` — Multi-Model Local OCR
Unifies high-throughput vision models without cloud API latency or costs:
```bash
# Auto-detects running server (defaults to LightOnOCR on :8085)
python3 ocr-cli/scripts/ocr.py slide_frame.png -o slide_frame.md

# Target specific backend
python3 ocr-cli/scripts/ocr.py document.pdf --engine lighton
python3 ocr-cli/scripts/ocr.py dense_paper.pdf --engine lighton --pages 1-3
python3 ocr-cli/scripts/ocr.py storefront.png --engine crispembed
```

### 2. `hybrid-browser` — Vision-Grounded Browser Agent
Automates complex web interactions using Chrome DevTools Protocol (CDP) inside rootless Podman containers, with DeskForge-Qwen3.5-4B visual fallback for Canvas/SVG elements:
```bash
python3 hybrid-browser/scripts/hybrid_browser.py "https://news.ycombinator.com" --action "read_headlines"
```

### 3. `video-miner` — ICM Video Mining Orchestrator
Extracts structured code and knowledge from video screencasts and lecture recordings using Interpretable Context Methodology (ICM):
```bash
# Initialize and step through review checkpoints
python3 video-miner/scripts/videomine.py init ./my_run "https://www.youtube.com/watch?v=..."
python3 video-miner/scripts/videomine.py step ./my_run
python3 video-miner/scripts/videomine.py run ./my_run
```

### 4. `jev-cli` — Calibrated Model Decisions
Queries local decision models for calibrated probability scores and triage labels:
```bash
python3 jev-cli/scripts/decide.py --choice "bug,feature,question" "The login button is broken"
```

---

## 🛠️ Server Launchers & Benchmarks

The [`launchers/`](launchers/) directory contains automated startup shell scripts and performance benchmarks for Vulkan and ROCm backends:
- `launchers/luffy_nothink.sh`: Starts Qwen3.6-35B on `:8080`
- `launchers/lighton-ocr.sh`: Starts LightOnOCR-3-1B on `:8085`
- `launchers/imajev-4b.sh`: Starts Imajev-4B on `:8083`
- `launchers/deskforge-qwen.sh`: Starts DeskForge grounding model on `:8088`

---

## 📚 Technical Documentation
- [Workstation Models & Service Directory](docs/models_and_services.md)
- [CSTR & CrispEmbed Model Suite Guide](docs/cstr_models.md)

---

## 📜 License
Licensed under the [MIT License](LICENSE).
