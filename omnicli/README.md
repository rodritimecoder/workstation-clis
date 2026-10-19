# omnicli

**The Uber OmniCLI** — one late-binding gateway to every tool on this
workstation. Discover by intent, pull one contract, invoke with a bounded
response.

Replaces the `local-hub` / `skills-hub` / `uber` entry points, which all
pointed at the same prototype.

---

## Install

```bash
ln -sfn /run/media/rodri/AI/workstation-clis/omnicli/omnicli.py ~/.local/bin/omnicli
ln -sfn /run/media/rodri/AI/workstation-clis/omnicli/omnicli.py ~/.local/bin/uber
```

`local-hub` and `skills-hub` remain as deprecated aliases.

---

## The loop

```bash
omnicli search "turn a recorded podcast into readable text"
omnicli tools audiocpp
omnicli describe audiocpp/scripts/audiocpp_cli
omnicli invoke audiocpp/scripts/audiocpp_cli asr speech.wav --json
```

Everything takes `--json` for agent consumption.

### `invoke` flag names

The gateway's own flags are prefixed `--omni-` so they never collide with the
target tool's flags — `--out`, `--project` and `--json` are all real flags on
real tools in this collection. Everything after the tool id that is not
`--omni-*` is passed to the tool untouched.

```bash
omnicli invoke local/decide --omni-project "answer,confidence" --omni-max-bytes 2000
omnicli invoke zoom-recorder/scripts/zoom_download --omni-buffer /tmp/zd.md -- --url "..."
```

| Flag | Effect |
|---|---|
| `--omni-buffer FILE` | write the full output to a file, print a preview |
| `--omni-project a,b` | keep only these JSON fields |
| `--omni-jq EXPR` | JQ filter expression |
| `--omni-grep RE` | keep only matching lines |
| `--omni-max-bytes N` | hard cap on returned bytes (default 8000) |
| `--omni-json` | wrap the result in JSON |

The cap is a guarantee, not a suggestion: the returned payload is never
larger than `--omni-max-bytes`, at any cap size.

---

## Layout

```
omnicli/
├── omnicli.py            # CLI entrypoint
├── catalog/              # the control plane
│   ├── builder.py        # indexer -> catalog.db
│   ├── search.py         # BM25 + coordination + optional re-ranker
│   ├── registry.py       # skill & tool discovery, --help contract extraction
│   ├── legacy.py         # the old substring scorer, kept for benchmarking
│   ├── textutil.py       # CJK bigram segmentation
│   ├── aliases.json      # hand-curated synonyms per skill
│   └── schema.sql
├── mcp/server.py         # Face B: JSON-RPC 2.0 over stdio, 4 meta-tools
├── scripts/              # llm_client.py, ocr.py, decide.py, asr.py
└── tests/
    ├── golden_eval.json  # 53 intent -> skill routing cases
    ├── eval_runner.py    # measures the catalog against the legacy scorer
    └── sweep.py          # tunes the weight constants
```

The catalog itself is a derived artifact and lives outside the repo:

```
~/.local/share/omnicli/catalog.db
```

Rebuild it with `omnicli index --rebuild`. It is rebuilt automatically
whenever the skill collection changes.

---

## Retrieval

```
BM25 (FTS5)  →  top-200 chunks
   ↓ per-skill aggregation: best chunk × bounded coverage bonus
   ↓ coordination factor: which DISTINCT query terms matched, weighted by
   ↓                      skill-level IDF (rare term ≫ common term)
top-N candidates
   ↓ optional embedding re-ranker (:8087) — reorders only, never recalls
top-K
```

The re-ranker is **optional and additive**. With every inference server down,
search still works: BM25 alone is the baseline, not a degraded mode.

Curated aliases live in their own FTS5 column with a much higher weight than
prose. A curated alias is the skill author stating "this vocabulary routes
here"; incidental body text matching the same word says far less, and must
not out-vote it.

---

## Verify

```bash
omnicli eval              # golden routing evaluation
omnicli eval --verbose    # per-case detail
```

```
BM25 catalog    top1 52/53 (98.1%)   top3 53/53 (100.0%)
legacy scorer   top1 34/53 (64.2%)   top3 40/53 (75.5%)
```

The one remaining miss is a genuine near-tie (0.23 points) between two
course-related skills, and the correct answer is still ranked #2.

`tests/overfit_check.py` audits the alias set against the eval set and
fails if any alias is a verbatim echo of a golden query — a router that is
handed the answer key measures nothing. It currently reports **0**.

---

## MCP

```bash
omnicli mcp
```

JSON-RPC 2.0 over stdio. Four meta-tools: `omni_discover`, `omni_describe`,
`omni_invoke`, `omni_status`. Hand-rolled stdlib transport — the required
subset is small and stable, and it keeps the control plane dependency-free.
