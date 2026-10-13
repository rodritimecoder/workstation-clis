---
name: ocr-cli
description: Multi-model local OCR for PDFs, slide decks, video keyframes, and images. Supports LightOnOCR-3-1B (:8085, fast video & slide OCR), NaviDC-OCR (:8082, dense PDF/scanned documents), and CrispEmbed (:8084, scene-text). Zero cloud API keys or telemetry.
---

# OCR CLI (`ocr-cli`)

High-performance local OCR suite unifying your local vision OCR models served via `llama-server` and custom backends.

---

## ⚡ Model Hierarchy & Ports

| Model | Port | Launcher Script | Best Suited For |
|---|---|---|---|
| **LightOnOCR-3-1B** | `:8085` | `launchers/lighton-ocr.sh` | **#1 Recommended**: Ultra-fast (~16k t/s prefill, ~330 t/s gen). Best for video slides, code snippets, lectures. |
| **SmolDocling-256M** | `:8084` / CLI | `cstr/smoldocling-GGUF` | **#2 Document Specialist**: Structured DocTags XML layout, markdown tables, formulas. |
| **NaviDC-OCR** | `:8082` | `launchers/navidc-ocr.sh` | Dense technical PDFs, multi-column research papers, books. |
| **CrispEmbed OCR** | `:8084` | `launchers/crispembed-ocr.sh` | Irregular scene text, logos, receipts, line crops (DBNet + PARSeq). |

---

## 🚀 Quick Usage

```bash
# 1. OCR a single image (uses default LightOnOCR on :8085)
python3 scripts/ocr.py slide.png

# 2. OCR a multi-page PDF using parallel batch extraction
python3 scripts/ocr.py lecture.pdf -o lecture.md

# 3. Target specific model port or engine
OCR_PORT=8082 python3 scripts/ocr.py scanned_paper.pdf
OCR_PORT=8085 python3 scripts/ocr.py video_frame.png

# 4. Check OCR server health and running backends
python3 scripts/ocr.py --doctor
```
