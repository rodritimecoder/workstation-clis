---
name: eval-router
description: >
  Self-calibrating request router with speculative shadow evaluation and failure harvesting
  (Glitch Cat Club; Reel DdWLJa2tjq6). Classifies prompt complexity (Easy/Moderate/Hard)
  using local Imajev-4B (:8083) and pure-Python learned weights, dispatches to local zero-cost models
  or free tiers, verifies output quality asynchronously or blocking with automated frontier fallback,
  and continuously harvests failures into training evaluations for 30-40% token cost reduction.
metadata:
  creator: kem_glitch
  source_reel:
    id: DdWLJa2tjq6
    url: https://www.instagram.com/reel/DdWLJa2tjq6/
    vault_note: kem_glitch/2026-10-17_self_calibrating_eval_router_and_shadow_verifier/notes.md
---

# Eval Router — Self-Calibrating Router & Speculative Evaluation Harness

```
   ┌────────────────────────────────────────────────────────┐
   │                  Incoming User Request                 │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │   Hybrid Classifier (Imajev-4B :8083 / ML)   │
        │   p(easy), p(moderate), p(hard) + Confidence │
        └──────┬──────────────────────┬──────────────┬─┘
               │                      │              │
      ┌────────▼────────┐    ┌────────▼────────┐   ┌─▼────────────────┐
      │   Easy (Free)   │    │  Moderate (Mid) │   │ Frontier Anchor  │
      │ Local / Nemotron│    │ Nemotron Ultra  │   │ Claude 3.7/Gemini│
      └────────┬────────┘    └────────┬────────┘   └─┬────────────────┘
               │                      │              │
               └──────────┬───────────┘              │
                          │                          │
                          ▼                          │
        ┌──────────────────────────────────────┐     │
        │     Speculative Shadow Evaluation    │     │
        │  Judge P(true) Quality Check :8083   │     │
        └──────┬───────────────────────────────┘     │
               │                                     │
       [PASS]  │                [FAIL]               │
       ────────┼───────────────────────────────────► │ (Transparent
               │                                     │  Frontier Swap)
               ▼                                     ▼
        Deliver Output                       Log to harvest.jsonl
        Log SQLite Savings                   Update Training Dataset
```

---

## ⚡ What It Solves (The Kem Glitch Architecture)
1. **The Cost Dilemma**: Sending simple formatting, typos, and straightforward scripts to expensive frontier models ($3–$15/M tokens) wastes 30–40% of API budgets.
2. **The Cheap Model Fear**: Developers avoid cheap or local models because they fear silent errors, truncation, or hallucinations.
3. **Speculative Shadow Verification**: Cheap models are used aggressively. In the background (or blocking), a lightweight judge evaluates response quality. If the cheap response fails, the frontier response replaces it *before anyone notices*, and the failure is harvested into a training dataset.
4. **Self-Improving Loop**: Every request becomes an evaluation. The system tracks real-world failure patterns and continuously refines its routing boundaries.

---

## 🛠️ CLI Quickstart

```bash
# Set alias or add to PATH
alias eval-router="python3 /run/media/rodri/AI/skills/eval-router/eval_router.py"

# 1. Route a prompt (Dry run - inspect tier, confidence, probabilities)
eval-router route "Fix the typo in README.md"

# 2. Execute with speculative evaluation and auto-fallback
eval-router exec "Write a python function to parse SemVer strings"

# 3. Buffer output to disk (Uber Protocol / Lean Context)
eval-router exec "Draft a detailed migration plan for Redis to Valkey" --out /tmp/plan.md

# 4. View real-time performance, pass rate, and dollar savings
eval-router stats

# 5. Inspect harvested failures for continuous model calibration
eval-router harvest

# 6. Re-train / calibrate weights from historical evaluations
python3 /run/media/rodri/AI/skills/eval-router/scripts/harvest.py --train
```

---

## 🌐 OpenAI-Compatible Proxy Server

You can point any coding assistant (Cursor, Claude Code, Cline, OpenCode, Agy) at `eval-router`:

```bash
python3 /run/media/rodri/AI/skills/eval-router/scripts/server.py --port 8088
```

Configure your tool:
- **Base URL**: `http://localhost:8088/v1`
- **Model**: `eval-router-auto`
- **API Key**: `any-key`

Every request received through `/v1/chat/completions` is automatically classified, routed to the optimal tier, shadow-evaluated, and logged with cost savings.

---

## 🏛️ Local Endpoints & Hardware Map

| Component | Target Port | Model / Engine | Role |
| :--- | :--- | :--- | :--- |
| **Classifier & Judge** | `:8083` | `Imajev-4B` via `jev-cli` | Calibrated P(true) quality judgement & 3-way triage |
| **Local Zero-Cost Tier** | `:8080` / `:4000` | Qwen3.6-35B Genesis / LiteLLM | Free local execution for Easy tier |
| **Cloud Free Tier** | OpenRouter Free | Nemotron 3.5 Lightning / Nemotron Ultra | Zero-quota offload |
| **Frontier Tier** | OpenRouter / Gemini | Claude 3.7 Sonnet / Gemini 2.5 Pro | High-complexity tasks and fallback swaps |

---

## 📊 Database Schema (`~/.config/eval-router/evals.db`)

Each execution appends to `evals`:
- `timestamp`: UTC execution time
- `prompt`: Input prompt
- `tier`: Classified tier (`easy` | `moderate` | `hard`)
- `confidence`: Classifier confidence score (0.0 to 1.0)
- `model_used`: Actual model executed
- `eval_passed`: 1 if output passed quality check, 0 if failed
- `fallback_model`: Name of frontier model if a speculative swap occurred
- `cost_saved_usd`: Dollar savings compared to frontier baseline
