---
name: frontend-uat

description: >
  Sub-second, model-backed frontend UAT loop (Glitch Cat Club / Kem Glitch; Reel DeKBMCQNRXU).
  Hands the page to the decision model as an indexed array of clickable targets, clicks
  deterministically over CDP, then reads the screen back to confirm the assertion — no
  open-ended text is ever generated, so a journey costs seconds and fractions of a cent
  instead of minutes and dollars. Use when running browser acceptance tests, driving a
  checkout or login flow, clicking a target by intent rather than by selector, or verifying
  a screen state after an action.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires the hybrid-browser CDP client (fast-cdp) on :9222 and the vllm-d3-mini decision server on :8083. Python 3.10+."
metadata:
  creator: "kem_glitch"
  source_reel_id: "DeKBMCQNRXU"
  source_reel_url: "https://www.instagram.com/reel/DeKBMCQNRXU/"
  source_reel_vault_note: "kem_glitch/2026-10-16_fast_frontend_uat_with_jev/notes.md"
allowed-tools: "Bash(frontend-uat:*) Bash(fast-cdp:*) Bash(python3:*) Read Write"
---

# Frontend UAT (`frontend-uat`)

Runs a browser acceptance test the way Reel [`DeKBMCQNRXU`](https://www.instagram.com/reel/DeKBMCQNRXU/)
does: **perception is a decision, not a generation.**

```
   [D] DOM candidate extraction  ──►  [P] decision model picks the target index
                                              │
        [D] CDP click on the chosen ref  ◄────┘
                    │
                    ▼
   [D] assert text/URL   ──or──  [P] model reads the screenshot back and answers
```

Each step is tagged `[D]` deterministic or `[P]` probabilistic, so a failure is
attributable to code or to a model turn.

| Path | Cost in the benchmark | Latency |
| :--- | :--- | :--- |
| Generative vision agent (multimodal LLM turn per click) | ~$7.00 per suite | minutes |
| This loop (decision model, no generated tokens) | ~$0.00024 per suite | seconds |

---

## 🛠️ CLI

Run from this skill's directory (the harness resolves paths from the skill root).

```bash
UAT="python3 scripts/frontend_uat.py"

# Is everything alive? (CDP browser on :9222, decision server on :8083)
$UAT doctor

# What can be clicked right now? (refs are what the model picks from)
$UAT candidates http://localhost:3000

# Decide before acting — writes a plan you can review or replay
$UAT plan --url http://localhost:3000 --intent "proceed to checkout" --out /tmp/checkout-plan.json

# The full loop: choose, click, verify
$UAT run --url http://localhost:3000 --intent "finish the payment and place the order" \
         --expect-text "Order confirmed" --screenshot /tmp/order.png

# Replay a reviewed plan (no second decision)
$UAT run --url http://localhost:3000 --intent "finish the payment and place the order" \
         --plan /tmp/checkout-plan.json --workdir .uat-ledger
```

`--json` prints the full report; `--out FILE` writes it to disk and keeps stdout to
one line, so a suite of runs costs a few tokens each. `--workdir DIR` serializes every
step (`step_01_candidates.json` … `step_04_verification.json`) for post-mortems.

**Exit codes:** `0` pass · `1` failed verification · `2` usage error · `3` a dependency is down.

---

## 🚦 This or `fast-cdp uat`?

`hybrid-browser` ships a **deterministic** `fast-cdp uat` that scores element labels
against the goal's words and deliberately calls no model. Reach for it first:

- Labels contain the intent's words → **`fast-cdp uat --goal …`**, zero model calls.
- The intent and the labels share no vocabulary, the element is only identifiable from
  the screenshot, or you are verifying a *visual* outcome → **this skill**.

The loop degrades honestly: the intent `"finish the payment and place the order"` against
labels `Back to catalog / Apply coupon / Complete purchase / Save for later` matches
**nothing** by keyword, and `Complete purchase` is what the model picks (p=0.9996).

---

## ⚠️ Gotchas

- **Extraction and action must see the same page.** The refs (`uat-1`, `uat-2`, …) are DOM
  order. A page that re-renders between `plan` and `run` shifts them — `run` re-validates
  the plan's URL and intent and refuses a mismatched plan, but a live SPA can still move
  under it. Re-plan if the page changed.
- **The ref must belong to the candidate set.** The loop fails loudly rather than clicking
  a ref the model invented.
- **`--assert-image` costs a model turn; `--expect-text`/`--expect-url` cost nothing.**
  Prefer an assertion the DOM can answer, and use the image gate only for outcomes that
  are visual (a toast, a chart, a modal that renders).
- **`--min-p` is the guard on a weak pick.** `confidence` from the engine is an entropy
  concentration, not a probability — the loop reports `p_selected`, the model's actual
  probability for the chosen target, and refuses to click below `--min-p`.
- **The decision server has 4 slots.** A UAT suite is dominated by clicks, not decisions;
  if you parallelise runs, more than four concurrent decisions will queue on :8083.

---

## 📚 Reference

`references/architecture.md` — the reel's architecture, benchmark economics, and why a
decision model beats a generative one for this job.
