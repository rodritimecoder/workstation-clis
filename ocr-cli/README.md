# ocr-cli

Multi-model local OCR engine for scanned PDFs, slide decks, video keyframes, document images, and scene text.

Zero cloud API keys, zero telemetry. Connects to local llama-server or CrispEmbed backends.

| Property | Detail |
|---|---|
| Script | `scripts/ocr.py` |
| Primary Engine (#1) | **LightOnOCR-3-1B** (`:8085`) — Ultra-fast video, slide, and dense text OCR |
| Document Engine (#2) | **SmolDocling-256M** (`cstr/`) — Structured DocTags layout, tables, formulas |
| Academic Engine (#3) | **NaviDC-OCR** (`:8082`) — Multi-column academic PDFs and scanned books |
| Scene Engine (#4) | **CrispEmbed Suite** (`:8084`) — Real-world scene text, receipts, line-level crops |
| Config | `OCR_ENGINE`, `OCR_PORT`, `OCR_HOST` |

---

## 🏆 Workstation OCR Rankings

1. **`LightOnOCR-3-1B` (and `LightOnOCR-3-4B`)** — **#1 Champion**
   - **Endpoint**: `http://127.0.0.1:8085` (launcher: `launchers/lighton-ocr.sh`)
   - **Strengths**: Lightning-fast prefill (~16k t/s) and generation (~330 t/s). Ideal for video-mining, slides, and code.
2. **`SmolDocling-256M` (`cstr/smoldocling-GGUF`)** — **#2 Document Understanding**
   - **Strengths**: 256M compact model generating structured DocTags XML markup (hierarchical headers, markdown tables, formulas).
3. **`NaviDC-OCR` (Q8_0 / Q5_K_M)** — **#3 Dense PDF Engine**
   - **Endpoint**: `http://127.0.0.1:8082` (launcher: `launchers/navidc-ocr.sh`)
   - **Strengths**: Coordinate-free natural reading order transcription for scanned academic PDFs.
4. **`CrispEmbed Suite` (`cstr/` DBNet + TrOCR / PP-OCRv6 / PARSeq)** — **#4 Scene Text & Crops**
   - **Endpoint**: `http://127.0.0.1:8084` (launcher: `launchers/crispembed-ocr.sh`)
   - **Strengths**: Ultra-low resource footprint for scene text, line crops, and screenshots.

---

## Quickstart

```bash
# Auto-detects running server (defaults to LightOnOCR on :8085)
python3 scripts/ocr.py slide_frame.png -o slide_frame.md

# Explicitly choose an engine
python3 scripts/ocr.py document.pdf --engine lighton
python3 scripts/ocr.py dense_paper.pdf --engine lighton --pages 1-3
python3 scripts/ocr.py storefront.png --engine crispembed

# Check server health and local models
python3 scripts/ocr.py --doctor
```

---

## Documentation
- Detailed model guide & rankings: [docs/models_and_services.md](../docs/models_and_services.md)
- CSTR & CrispEmbed suite: [docs/cstr_models.md](../docs/cstr_models.md)
