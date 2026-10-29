---
name: omnicli

description: "On-demand gateway to every tool on this workstation — the index behind the shelf, not a front line. Find the right tool by intent with BM25 full-body search over all skill bodies, pull one tool's exact contract, and invoke it with a bounded response. Also fronts the local inference endpoints: Genesis 35B coder (:8080), LightOnOCR (:8085), vllm-d3-mini calibrated decisions (:8083), Nemotron ASR (:8081). Installed, supported and used directly; `status: archived` only keeps it out of automatic harness discovery and out of the published bundles, because the plain Agent Skills shelf is the default front line."
status: archived

compatibility: "Requires the local inference servers it fronts: :8080, :8081, :8083, :8084 and :8085, plus the optional embedding server :8087 used to re-rank search results (the catalog works without it). The decision port speaks either native /v1/systemone or the pplx-decider joint protocol v3; the protocol is auto-detected from the served model."
allowed-tools: "Bash(omnicli:*) Read"
---

# `omnicli` — The Uber OmniCLI

> **On demand, not a front line.** Since 2026-10-20 harnesses discover the
> plain Agent Skills shelf first, so this skill is not auto-routed and is not
> published to the bundles. It is installed (`~/.local/bin/omnicli`),
> supported, and called directly whenever the shelf is ambiguous; select
> gateway mode instead and it *becomes* the front line. The mode is a one-line
> state file (`~/.config/skills-frontline`) that `sync-skills` reads; there is
> no `skills-frontline` command. It remains the only thing that can answer
> "which of the 433 catalogued tools does this intent want". The two front
> lines were compared on 61 golden routing queries with the same model picking
> both ways — shelf 54/61, gateway 60/61. See
> `docs/front-line-shelf-vs-gateway.md` in the canonical repository.

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
                        │  433 tools  (data plane)       │
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
🔍 [omnicli] intent: 'transcribe a zoom lecture recording'   tier=bm25(gated)

  1. zoom-recorder   score=0.91  lex=34.25  coord=0.75  chunks=22
       zoom-recorder/scripts/zoom_download
       Download transcripts, audio, and visual keyframe slides from Zoom cloud...
       → omnicli tools zoom-recorder
```

### The re-ranker is gated, not always on

BM25 plus curated aliases is near-saturated on the golden set (60/61 top-1),
and the semantic re-ranker changes the top hit on **none** of those 61 cases.
So it runs only when the lexical ranking is unsure: the gap between the top two
hits, relative to the top score, falls below `RERANK_GATE_MARGIN` (0.25).

| mode | latency | golden top-1 | fires on |
|---|---|---|---|
| `--rerank never` | 4.0 ms | 60/61 | 0/61 |
| `--rerank auto` (default) | 24 ms | 60/61 | 9/61 |
| `--rerank always` | 126 ms | 60/61 | 61/61 |

Same accuracy, 6x less latency. The re-ranker itself is `bge-small-en-v1.5`
on the local embedding endpoint, running with `-ngl 0` — **CPU only, zero
VRAM**. When the embedding server is down, `auto` falls back to `bm25(gated)`
and the catalog stays fully usable.

### Discovery does not imply exposure

A tool is catalogued the moment it is discovered, and runnable only once it
has been enabled. `omnicli tools` marks disabled tools, `omnicli describe`
still returns their contract, and `omnicli invoke` refuses them with the exact
command that would open the gate:

```bash
omnicli policy            # 367/433 enabled, plus the recent decisions
omnicli enable <tool_id>  # record the decision against the contract hash
omnicli disable <tool_id>
```

Tools that existed when the gate was introduced were grandfathered; tools new
relative to the previous catalog start disabled. The decision log
(`policy.log.jsonl`) is append-only and survives a rebuild.

### 2. `omnicli describe <tool_id>` — get one contract

```bash
omnicli describe zoom-recorder/scripts/zoom_download
```

Returns the usage line, every flag, positionals and subcommands — extracted
from the tool's own `--help` at index time. **One** tool per call.

Given a **skill name** instead of a tool id, it returns the skill itself: its
frontmatter and a section outline, with a token estimate per section. Add
`--section "<heading>"` to read just that one section.

```bash
omnicli describe canvas-cli
# 📖 [canvas-cli]  ~739 tokens, 13 sections, 22 tools
#    Sections:
#      Canvas LMS (`canvas-cli`)                          60 tok
#        🏛️ The Command Groups                            187 tok
#        🛡️ Token Shielding                               121 tok
#    Read one:  omnicli describe canvas-cli --section "token shield"

omnicli describe canvas-cli --section "token shield"
# 📖 [canvas-cli] section: 🛡️ Token Shielding  (~121 tokens)
```

This is the spec's progressive disclosure, routed through the gateway: the
outline first, then one section. A skill's body is never fetched whole unless
that is what you ask for.

The skills themselves are **never modified**. The catalog is an index over
them: it reads the files, it does not own them. Delete `catalog.db` and every
skill still works exactly as before.

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
| `--omni-buffer FILE` | write the full, **unfiltered** stdout to a file, print a preview |
| `--omni-project a,b.c` | keep these JSON fields; dotted paths and list elements supported |
| `--omni-jq EXPR` | JQ filter expression |
| `--omni-grep RE` | keep only matching lines |
| `--omni-max-bytes N` | hard cap on returned bytes (default 8000) |
| `--omni-json` | wrap the result in JSON |

A cap is a budget to fill, not a reason to return only a banner: at 250 bytes
the reply is 250 bytes of head, banner and tail. A projection that cannot be
applied says so; it never returns the unfiltered payload as though it worked.
Unknown `--omni-*` flags are reported instead of silently dropped.

---

## 🔌 Face B — the MCP server

```bash
omnicli mcp          # JSON-RPC 2.0 over stdio
```

Exposes four meta-tools, so a tool-calling agent sees ~400 tokens of
startup instead of 150,000:

| Tool | Input | Returns |
|---|---|---|
| `omni_discover` | `intent`, `limit` (default 5), `rerank`, `max_bytes` | compact routing view: skill, score, why, best tool ids |
| `omni_describe` | `tool_id`, `section`, `doc`, `max_bytes` | the exact contract for that one tool, or a skill's outline / one section |
| `omni_invoke` | `tool_id`, `args`, `projection`, `jq`, `grep`, `max_bytes`, `timeout` | bounded, projected result |
| `omni_status` | `max_bytes` | endpoint health, catalog freshness, enable count, retrieval tier |

Every reply is bounded by `max_bytes`, not just `omni_invoke`; an oversized
reply becomes a structured error rather than unparseable truncated JSON.
Requests run on a small pool, so a slow tool cannot stall `ping`.

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
| `omnicli decide "<state>" "<q>"` | `local/decide` | the decision model on :8083, protocol auto-detected (pplx-decider-flash v1.2 or vllm-d3-mini) |
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
BM25 catalog    top1 60/61 (98.4%)   top3 60/61 (98.4%)
legacy scorer   top1 35/61 (57.4%)   top3 46/61 (75.4%)
```

The miss is a generic-token query ("decide which model should handle this
prompt before answering") where the decision skill matches all six tokens and
the router matches four; the re-ranker does not separate them either. It is
recorded, not excluded.

The alias set is audited against the eval set (`tests/overfit_check.py`) so a
router handed the answer key cannot be mistaken for a router that works. It
currently reports **0** echoes; three verbatim-echo aliases were removed, and
the case one of them propped up is the miss above. `omnicli eval --rerank
auto|always|never` re-runs the set under any re-ranker mode; all three
currently score 60/61.

### Token cost (measured)

`tests/measure_tokens.py` counts what actually lands in the model's context,
using the local Qwen3.5 tokenizer against the 45-skill library:

| | prompt shelf | omnicli | |
|---|---|---|---|
| selection phase | 8,208 tok | 691 tok | **91.6% smaller** |
| to invoke one tool | 9,326 tok | 2,890 tok | **69.0% smaller** |

The second row's saving comes from the 8 KB response cap, not from the
discovery itself. The selection-phase number is the one that matters, because
it is paid on every turn whether or not a tool gets used.

---

## 🔌 Compatibility

`uber`, `local-hub` and `skills-hub` are **not** installed any more; they were
deprecated aliases and have been removed from `PATH`. `omnicli` is the name.
The legacy `search` / `tools` / `inspect` / `run` verbs still work; `search`
uses the BM25 catalog instead of the old substring scorer.
