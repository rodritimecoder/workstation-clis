---
name: ocr-cli
description: Multi-model local OCR for PDFs, slide decks, video keyframes, and images. Primary engine: LightOnOCR-3-1B (:8085, ultra-fast video & slide OCR, layout extraction), SmolDocling-256M (DocTags layout), and CrispEmbed (:8084, scene-text). Zero cloud API keys or telemetry.
---

# OCR CLI (`ocr-cli`)

High-performance local OCR suite unifying local vision OCR models served via `llama-server` and custom backends, with **LightOnOCR-3-1B** as the flagship default.

---

## ⚡ Model Hierarchy & Ports

| Model | Port | Launcher Script | Best Suited For |
|---|---|---|---|
| **LightOnOCR-3-1B** | `:8085` | `launchers/lighton-ocr.sh` | **#1 Flagship**: Ultra-fast (~16k t/s prefill, ~330 t/s gen). Video slides, code snippets, lectures, documents. |
| **SmolDocling-256M** | `:8084` / CLI | `cstr/smoldocling-GGUF` | **#2 Document Specialist**: Structured DocTags XML layout, markdown tables, formulas. |
| **CrispEmbed OCR** | `:8084` | `launchers/crispembed-ocr.sh` | **#3 Scene Text**: Irregular scene text, logos, receipts, line crops (DBNet + PARSeq). |
| **NaviDC-OCR** | `:8082` | `launchers/navidc-ocr.sh` | Legacy dense technical PDFs, multi-column research papers. |

---

## 🚀 Quick Usage

```bash
# 1. OCR a single image (uses default LightOnOCR on :8085)
python3 scripts/ocr.py slide.png

# 2. OCR a multi-page PDF using parallel batch extraction
python3 scripts/ocr.py lecture.pdf -o lecture.md

# 3. Target specific engine
python3 scripts/ocr.py video_frame.png --engine lighton
python3 scripts/ocr.py storefront.png --engine crispembed

# 4. Check OCR server health and running backends
python3 scripts/ocr.py --doctor
```
