---
name: omnicli

description: "Unified late-binding gateway to every tool on this workstation. Find the right tool by intent with BM25 full-body search over all skills, pull one tool's exact contract, and invoke it with a bounded response. Also exposes the local inference endpoints: Genesis 35B coder (:8080), LightOnOCR (:8085), vllm-d3-mini calibrated decisions (:8083), Nemotron ASR (:8081)."

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires the local inference servers it fronts: :8080, :8081, :8083, :8084 and :8085."
metadata:
  author: "rodri"
allowed-tools: "Bash(omnicli:*) Read"
---

# `omnicli` — The Uber OmniCLI

One gateway, two faces, one catalog. An agent discovers a tool by *intent*,
pulls the contract for that one tool, invokes it, and gets a bounded response.
Nothing else enters the context window.

```
                  ┌── Face A: CLI (shell harnesses) ──────────────┐
   agent ────────▶│  omnicli search | describe | invoke | status │
                  └── Face B: MCP stdio (tool-calling agents) ────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │  catalog.db  (control plane)   │
                        │  FTS5 BM25 + weighted aliases  │
                        │  optional embedding re-ranker  │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │  210 tools  (data plane)       │
                        │  scripts · CLIs · endpoints    │
                        └───────────────────────────────┘
```

---

## ⚡ The discovery loop

### 1. `omnicli search "<intent>"` — find the tool

```bash
omnicli search "transcribe a zoom lecture recording"
omnicli search "turn a recorded podcast into readable text"
omnicli search "调研一下这个话题在网上的讨论"
```

BM25 over the **full body** of every skill, with hand-curated aliases in a
separately weighted column. A curated alias ("podcast" → audio tooling) is
deliberate author intent and outranks incidental prose.

```
🔍 [omnicli] intent: 'transcribe a zoom lecture recording'   tier=bm25

  1. zoom-recorder   score=29.20  coord=0.77  chunks=20
       zoom-recorder/scripts/zoom_download
       Download transcripts, audio, and visual keyframe slides from Zoom cloud...
       → omnicli tools zoom-recorder
```

### 2. `omnicli describe <tool_id>` — get one contract

```bash
omnicli describe zoom-recorder/scripts/zoom_download
```

Returns the usage line, every flag, positionals and subcommands — extracted
from the tool's own `--help` at index time. **One** tool per call.

### 3. `omnicli invoke <tool_id> [args]` — run it, bounded

```bash
omnicli invoke zoom-recorder/scripts/zoom_download -- --url "https://zoom.us/rec/abc"

# keep only the fields you need
omnicli invoke local/decide --omni-project "answer,confidence"

# keep the full payload on disk, read only what matters
omnicli invoke local/llm --omni-buffer /tmp/out.md
```

**Every response is capped** (default 8 KB) with a head+tail preview and a
pointer to the full output. An agent cannot flood its context window by
forgetting a flag.

**Flag names are prefixed `--omni-`** so they never collide with the target
tool's own flags (`--out`, `--project` and `--json` are all real flags on
real tools here). Anything after the tool id that is *not* `--omni-*` is
passed to the tool untouched; `--` forces that split explicitly.

| Flag | Effect |
|---|---|
| `--omni-buffer FILE` | write the full output to a file, print a preview |
| `--omni-project a,b` | keep only these JSON fields |
| `--omni-jq EXPR` | JQ filter expression |
| `--omni-grep RE` | keep only matching lines |
| `--omni-max-bytes N` | hard cap on returned bytes (default 8000) |
| `--omni-json` | wrap the result in JSON |

---

## 🔌 Face B — the MCP server

```bash
omnicli mcp          # JSON-RPC 2.0 over stdio
```

Exposes four meta-tools, so a tool-calling agent sees ~400 tokens of
startup instead of 150,000:

| Tool | Input | Returns |
|---|---|---|
| `omni_discover` | `intent`, `limit` | ranked skill + tool ids, one line each |
| `omni_describe` | `tool_id` | the exact contract for that one tool |
| `omni_invoke` | `tool_id`, `args`, `projection` | bounded, projected result |
| `omni_status` | — | endpoint health, catalog freshness, retrieval tier |

Register it with a client:

```json
{ "mcpServers": { "omnicli": {
  "command": "omnicli", "args": ["mcp"] } } }
```

---

## 🧠 Native local inference

Available both as subcommands and as tools in the catalog:

| Command | Tool id | Model |
|---|---|---|
| `omnicli llm "<prompt>"` | `local/llm` | Qwen3.6-35B Genesis, dual-GPU (:8080) |
| `omnicli ocr <file>` | `local/ocr` | LightOnOCR-3-1B (:8085) |
| `omnicli decide "<state>" "<q>"` | `local/decide` | vllm-d3-mini, calibrated (:8083) |
| `omnicli asr transcribe <audio>` | `local/asr` | Nemotron-3.5 ASR (:8081) |

```bash
omnicli status            # ports, catalog freshness, retrieval tier
omnicli index --rebuild   # rebuild the catalog
omnicli eval              # golden routing evaluation
```

---

## 🧭 Why this exists

Thirty-plus skills, each with its own `SKILL.md`, used to be a prompt shelf.
The Databricks skill-shadowing study measured the cost: correct skill
selection fell from 88% to 52.6% as the library grew, with **two thirds of
the failures caused by picking wrong or picking nothing** — not by token
count. The router had to evaluate dozens of frontmatter descriptions on turn 0.

Retrieval beats installation. The catalog moves selection off the model's
shoulders and onto a BM25 index, and the golden evaluation in `tests/` is the
falsifiable claim that it works:

```
BM25 catalog    top1 52/53 (98.1%)   top3 53/53 (100.0%)
legacy scorer   top1 34/53 (64.2%)   top3 40/53 (75.5%)
```

The alias set is audited against the eval set (`omnicli eval` / 
`tests/overfit_check.py`) so a router handed the answer key cannot be
mistaken for a router that works.

---

## 🔌 Compatibility

`uber`, `local-hub` and `skills-hub` remain as aliases for `omnicli`. The
legacy `search` / `tools` / `inspect` / `run` verbs still work; `search` now
uses the BM25 catalog instead of the old substring scorer.
