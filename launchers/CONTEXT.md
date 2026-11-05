# Model Server Ports & Schema Contract (`/run/media/rodri/AI/sh/CONTEXT.md`)

Operational specifications, port mappings, and weights contracts for all local inference endpoints.

---

## 1. Port Registry & Backend Slots

| Port | Slot | Cardinality | Default Model | Launcher | Purpose / Capability |
|---|---|---|---|---|---|
| `:8080` | `llm` | Multi (13) | Qwen3.6-35B-A3B-Uncensored-Genesis | `luffy_nothink.sh` | Primary coding & generative LLM |
| `:8081` | `audio` | Multi (3) | nemotron-asr / crisperwhisper | `run-audiocpp.sh` | STT, TTS, forced alignment, voice cloning |
| `:8082` | `decision-engine` | Single (1) | StartLux-Decision-v1.1-4B | `startlux-decision.sh` | Experimental decision engine |
| `:8083` | `decision` | Multi (6) | h2o-lightning-4b | `h2o.sh` | Calibrated non-generative decisions (bool/choice/score) |
| `:8084` | `ocr-crispembed` | Single (1) | CrispEmbed (PP-OCRv6) | `crispembed-ocr.sh` | Bounding boxes, document layout, OCR |
| `:8085` | `ocr-lighton` | Single (1) | LightOnOCR-3-0.8B | `lighton-ocr.sh` | Fast Markdown OCR for slides, code, PDFs |
| `:8086` | `reranker` | Single (1) | jina-reranker-v2-base | `jina-reranker.sh` | Cross-encoder reranking for hybrid RAG |
| `:8087` | `embed` | Multi (2) | bge-small-en-v1.5 | `bge-small.sh` | Dense vector embeddings (384d) for semantic cache |
| `:8088` | `grounding` | Single (1) | WeVisOne-VL-4B | `wevisone-vl.sh` | Visual grounding & UI locator boxes |
| `:8089` | `decision-fallback`| Single (1) | Imajev-4B | `imajev-decider.sh` | Secondary decision engine |
| `:8090` | `ocr-jev` | Single (1) | MiniCPM-OCR-Jev | `minicpm-ocr-jev.sh` | One-pass OCR consistency gate (P(faithful)) |
| `:8091` | `llm-rp` | Single (1) | LFM3-1.7B-Uncensored-AD | `lfm3-1.7b-uncensored.sh` | Short-form / creative / auxiliary LLM |

---

## 2. Shared Weights & Binaries
- **GGUF Models Directory:** `/run/media/rodri/AI/models/`
- **llama.cpp Build:** `/run/media/rodri/AI/llama.cpp/build/bin/` (`llama-server`, `llama-mtmd-cli`)
- **audiocpp CLI:** `/home/rodri/.local/bin/audiocpp`
