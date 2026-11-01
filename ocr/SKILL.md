---
name: ocr

description: >
  Unified OCR hub on dual AMD Radeon GPUs: LightOnOCR-3-0.8B (:8085) transcribes documents,
  PDFs, screenshots and video slides into structured Markdown; CrispEmbed (:8084) returns 2D
  spatial coordinates and text tokens for scene text and UI elements. Use to read text out of
  an image, screenshot or scanned page, to OCR a PDF or slide deck, or to get bounding boxes
  for words on screen. To locate a described object rather than read its text, use clip-box;
  for layout-typed regions, tables and formulas, use doc-layout.

compatibility: "Requires Dual AMD Radeon RX 9060 XT GPUs with Vulkan, plus the LightOnOCR server on :8085 and CrispEmbed on :8084."
allowed-tools: "Bash(ocr:*) Bash(python3:*) Read Write"
---

> **Model layer:** the server behind this skill is registered in the `model-layer` skill (slot `:8084 + :8085`) — launcher, weights files, health and quirks. Read it before starting, swapping or debugging the model.

# `ocr` — Unified Premier OCR Hub

A unified, hardware-accelerated OCR toolchain on **Dual AMD Radeon RX 9060 XT** GPUs, combining:
1. **LightOnOCR-3-0.8B (Premier Engine, `:8085`)**: The flagship model for high-throughput document, PDF, screenshot, and video slide transcription into structured Markdown.
2. **CrispEmbed (Spatial Engine, `:8084`)**: PP-OCRv6 DB++ / DBNet for detecting 2D spatial coordinates `[x1, y1, x2, y2]`, text tokens, and UI button locations.

---

## 🛠️ Deterministic CLI Quickstart

The canonical executable is located at `~/.local/bin/ocr` (and `~/.local/bin/ocr-cli`, symlinked from `/run/media/rodri/AI/skills/ocr/ocr.py`).

### 1. Premier Document & Slide OCR (LightOnOCR-3-0.8B)
```bash
# Clean UNIX stdout: returns only transcribed Markdown text
ocr slide.png > slide.md

# Transcribe a multi-page PDF document
ocr document.pdf --pages 1-5 -o output.md

# Output machine-readable typed JSON (--json)
ocr slide.png --json
# Output:
# {
#   "task": "document_ocr",
#   "engine": "lighton",
#   "file": "/path/to/slide.png",
#   "pages_count": 1,
#   "text": "LLaMA C++\n\nCan it run **BBSM** LLaMA?",
#   "markdown": "LLaMA C++\n\nCan it run **BBSM** LLaMA?",
#   "latency_ms": 539.3,
#   "source": "lighton_1b_server"
# }
```

### 2. Spatial Scene-Text & Bounding Boxes (CrispEmbed)
```bash
# Extract 2D bounding boxes and coordinates
ocr screenshot.png --boxes

# Output:
# 📍 [455.4, 340.7, 1123.3, 388.6] (94.5%) -> Confirm Order
# 📍 [120.0, 45.0, 210.0, 85.0] (98.2%) -> Cancel

# Output machine-readable spatial JSON (--json)
ocr spatial screenshot.png --json
# Output:
# {
#   "task": "spatial_ocr",
#   "engine": "crispembed",
#   "image": "/path/to/screenshot.png",
#   "n_regions": 2,
#   "results": [
#     {
#       "text": "Confirm Order",
#       "bbox": [455.4, 340.7, 1123.3, 388.6],
#       "confidence": 0.9449
#     }
#   ],
#   "latency_ms": 120.4
# }
```

### 3. Server Daemons & Doctor
```bash
# Check status of both engines
ocr doctor [--json]

# Manage background daemons
ocr server status
ocr server start --engine lighton
ocr server stop --engine all
```

---

## 🏛️ Architecture & Endpoints

| Capability | Engine | Port | Format | Specialty |
|---|---|---|---|---|
| **Document / PDF / Slide** | **LightOnOCR-3-0.8B** | `:8085` | Structured Markdown | flagship text OCR (thinking variant — output in `reasoning_content`) |
| **Spatial Scene Text / UI** | **CrispEmbed (PP-OCRv6)** | `:8084` | 2D Bounding Boxes `[x1, y1, x2, y2]` | Sub-second spatial UI detection for `frontend-uat` |
