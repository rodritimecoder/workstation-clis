---
name: eval-pipeline
description: >
  Step-level propagation risk mitigation and intermediate artifact ledger (Glitch Cat Club / Kem Glitch;
  Reel DeHK65INHqh). Tags every step explicitly as [D] (Deterministic Code), [P] (Probabilistic Model), or [H] (Human),
  forcing disk serialization of intermediate states (step_01.json) and halting compound downstream failures via
  automated assertion gates.
metadata:
  creator: kem_glitch
  source_reel:
    id: DeHK65INHqh
    url: https://www.instagram.com/reel/DeHK65INHqh/
    vault_note: kem_glitch/2026-10-16_eval_pipeline_and_propagation_risk/notes.md
---

# Eval Pipeline (`eval-pipeline`)

Step-level propagation risk shield derived from **Kem Glitch (Glitch Cat Club)**'s architecture in Reel [`DeHK65INHqh`](https://www.instagram.com/reel/DeHK65INHqh/).

---

## 🏛️ The Tripartite Step Taxonomy

1. **`[D]` Deterministic Code**: Fast, cheap, exact (AST parsing, schema checking, regex).
2. **`[P]` Probabilistic Model**: Generative synthesis, clustering, semantic inference.
3. **`[H]` Human in the Loop**: Final sign-off or subjective taste.

An unchecked drift in Step 1 poisons all downstream steps (**Propagation Risk**). By serializing intermediate artifacts to disk and asserting boundaries at each handoff, failures halt immediately at the exact failing step.

---

## 🛠️ CLI Quickstart

```bash
PIPE="python3 /run/media/rodri/AI/skills/eval-pipeline/eval_pipeline.py"

# 1. Audit recorded step artifacts in ledger
$PIPE audit --ledger-dir .eval_ledger

# 2. Run self-diagnostic verification pipeline
$PIPE verify-sample
```
