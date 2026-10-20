---
name: openrouter-free

description: >
  Delegate autonomous coding subagent loops, compound bash batching, text embeddings,
  calibrated decision routing, and TTS audio synthesis to verified free OpenRouter endpoints
  (NVIDIA Nemotron Ultra/Lightning, Inception Mercury Decide, Fish Audio, LFM Embed)
  with Homelab priority and Gemini failover.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires network access to openrouter.ai and an API key (OPENROUTER_API_KEY). The optional Gemini tier needs GEMINI_API_KEY."
metadata:
  author: "rodri"
allowed-tools: "Bash(openrouter-free:*) Bash(python3:*) Read Write"
---

# OpenRouter Free Multimodal & Subagent Skill (`openrouter-free`)

Use this skill to delegate self-contained coding loops, multi-command bash workflows, calibrated decisions, vector embeddings, and speech synthesis to verified zero-cost endpoints without exhausting primary frontier token quotas.

## Verified Free Endpoint Catalog
- **Note-Taking & Synthesis**: `dots-studio/dots-3-note-preview:free` (Reasoning note synthesis)
- **Agentic Reasoning & Chat**: `thinkingmachines/inkling:free` (Thinking Machines agentic free tier)
- **Reasoning & Code (Heavy)**: `nvidia/nemotron-3-ultra-550b-a55b:free`
- **Fast Subagent Coding**: `nvidia/nemotron-3.5-lightning:free`
- **General Free Router**: `openrouter/free`
- **Calibrated Decisions**: `inception/mercury-decide:free`
- **Vector Embeddings**: `liquid/lfm-2.5-embedding-350m:free` & `nvidia/llama-nemotron-embed-vl-1b-v2:free`
- **Neural Reranking**: `nvidia/llama-nemotron-rerank-vl-1b-v2:free`
- **TTS Speech Audio**: `fish-audio/s2.1-pro-free:free`
- **Automatic Fallback**: Local Homelab -> Free High-Reasoning -> Dynamic Free -> Google AI Studio (`gemini-3.5-flash-lite` / `gemini-2.0-flash`)

## Prerequisites
- `OPENROUTER_API_KEY`: Required (`sk-or-v1-...`).
- `GEMINI_API_KEY`: Optional fallback if OpenRouter free tiers hit rate limits.
- `HOMELAB_LITELLM_URL`: Optional local proxy to prioritize local hardware first.

---

## The Uber Protocol: Micro-Batching & Response Projection

1. **Compound Script Batching (`run_bash_batch`)**: Subagents execute ordered arrays of shell commands inside a single compound bash environment (`set -eo pipefail`). Commands share working directory context (`cd` sticks) and halt on fatal errors.
2. **Response Projection & Disk Buffering**: Never blast large embedding vectors or verbose subagent traces into primary LLM context. Use `--out`, `--project <fields>`, or `--jq <expr>` to buffer results to disk (e.g. `/tmp/`), keeping the main conversation lean.
3. **Canonical Executable**: `openrouter-free` in `~/.local/bin/openrouter-free` (symlinked from `/run/media/rodri/AI/skills/openrouter-free/scripts/or_agent.py`).

---

## CLI Usage Patterns

### 1. Diagnostic Health Check & Free Tier Telemetry (`doctor`)
Inspects live API key validity, daily free quota remaining (out of 1,000 requests), and local homelab fallback readiness:
```bash
# Pretty-printed health report
openrouter-free doctor

# Machine-readable JSON telemetry for automated agents
openrouter-free doctor --json

# Run live sub-second inference probe to verified free endpoints
openrouter-free doctor --live
```

### 2. Autonomous Coding Subagent (`agent`)
Runs a multi-turn subagent with compound command batching:
```bash
openrouter-free agent \
  --prompt "Inspect src/parser.ts, fix handling of empty arrays, run tests, and summarize." \
  --model "nvidia/nemotron-3.5-lightning:free" \
  --out /tmp/subagent_report.md
```

### 3. Single-Turn Code Review or Architecture Query (`chat`)
Fast, tool-free completion for diffs or second opinions:
```bash
openrouter-free chat \
  --prompt "Audit this git diff for memory leaks: $(git diff)" \
  --model "nvidia/nemotron-3-ultra-550b-a55b:free" \
  --project content
```

### 4. Calibrated Decision Routing (`decide`)
Discrete triage and confidence scoring via Mercury Decide with optional field projection:
```bash
# Full response
openrouter-free decide \
  --query "Is this pull request safe to deploy immediately?" \
  --options "deploy_now" "needs_human_review" "block_build"

# Projected verdict and confidence only
openrouter-free decide \
  --query "Is 100 greater than 10?" \
  --options "yes" "no" \
  --project verdict,confidence
```

### 5. Batched Vector Embeddings (`embed`)
Embeds an array of strings or file contents in 1 single HTTP request with disk buffering:
```bash
openrouter-free embed \
  --inputs "First text chunk" "Second chunk" "README.md" \
  --out-json /tmp/embeddings.json
```

### 6. Text-to-Speech Generation (`tts`)
Generates speech audio from text using Fish Audio Free:
```bash
openrouter-free tts \
  --text "Subagent verification completed successfully. All tests passing." \
  --out /tmp/status.mp3
```
