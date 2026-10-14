---
name: graph-memory
description: "Local graph-memory RAG and distillation engine: hybrid BM25 + BGE-small-en-v1.5 (384d) reciprocal rank fusion over notes, with exact-quote LLM distillation. Use whenever asked to index notes, search knowledge, query memory, or recall context using local llama-server endpoints."
compatibility: "Linux, Python 3 stdlib (urllib, sqlite3, struct, json). Embedding on :8082 (bge-small-en-v1.5-f16.gguf), LLM completions on :8000/:8080 (Qwen3.6-35B)."
---

# Graph Memory — Local Hybrid RAG & Exact-Quote Distillation

A zero-dependency local RAG and memory system adapted from Glitch Cat Club's `graph-memory-starter`.

## Key Capabilities
1. **Hybrid Reciprocal Rank Fusion (K=60)**:
   - **Keyword Leg**: SQLite FTS5 with BM25 ranking.
   - **Meaning Leg**: 384-dimensional cosine similarity via local `bge-small-en-v1.5` embeddings (`http://127.0.0.1:8082/v1/embeddings`).
   - **Symmetric Search**: Query prefixes omitted to ensure search symmetry.
2. **Exact-Quote Distillation**:
   - Distills markdown notes into question-rule-quote triplets via local `llama-swap` (`http://127.0.0.1:8000/v1/chat/completions` running `Qwen3.6-35B` at `temperature: 0.0`).
   - Strict quote verification invariant: `normalise(quote) in normalise(source)`. If a quote is not verbatim, the entry is dropped to prevent hallucinations.
3. **Zero Heavy Dependencies**:
   - Uses Python standard library (`urllib.request`, `sqlite3`, `struct`, `json`, `hashlib`). No `fastembed` or external pip packages required.

## Commands

### Search the Index
```bash
python3 /run/media/rodri/AI/skills/graph-memory/rag/search.py "<your query>"
```

### Rebuild Index over Notes
```bash
python3 /run/media/rodri/AI/skills/graph-memory/rag/build_index.py --corpus "/run/media/rodri/AI/University/notes"
```

### Distil Notes into Question-Quote Triplet Memory
```bash
python3 /run/media/rodri/AI/skills/graph-memory/rag/distil.py "/run/media/rodri/AI/University/notes" [--limit N]
```

## Local Inference Endpoints
- **Embeddings**: `http://127.0.0.1:8082/v1/embeddings` (`bge-small-en-v1.5-f16.gguf`)
- **Chat Distillation**: `http://127.0.0.1:8000/v1/chat/completions` (or `:8080`, `qwen3.6-35b`)
