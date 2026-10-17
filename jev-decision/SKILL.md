---
name: jev-decision
description: >
  Calibrated decision engine and sub-second visual UAT runner (Glitch Cat Club / Kem Glitch;
  Reels DdjOqRYNZZi, DeMSV1jNYem, DeKBMCQNRXU). Decouples perception from open-ended generative tokens
  into 3 universal primitives: bool (binary), choice (constrained enum), and score (scalar magnitude 0.0-1.0).
  Delivers high-throughput context de-duplication (41k decisions in 7 mins for $0.37) and frontend acceptance testing.
metadata:
  creator: kem_glitch
  source_reels:
    - id: DdjOqRYNZZi
      url: https://www.instagram.com/reel/DdjOqRYNZZi/
      vault_note: kem_glitch/2026-10-16_jev_decision_engine/notes.md
    - id: DeMSV1jNYem
      url: https://www.instagram.com/reel/DeMSV1jNYem/
      vault_note: kem_glitch/2026-10-16_jev_review_and_decision_types/notes.md
    - id: DeKBMCQNRXU
      url: https://www.instagram.com/reel/DeKBMCQNRXU/
      vault_note: kem_glitch/2026-10-16_fast_frontend_uat_with_jev/notes.md
---

# JEV Decision Engine (`jev-decision`)

A calibrated, non-generative decision system implementing Kem's (Glitch Cat Club) **3 Universal Decision Primitives**, backed by the premier **OneJev1.5-4B Multimodal Vision Model** (`prithivMLmods/OneJev1.5-4B-GGUF` + `OneJev1.5-4B.mmproj-bf16.gguf` on `:8083`). Solves the latency, cost, and stochastic drift of asking frontier generative models to answer discrete, structured questions.

---

## 🏛️ The Universal Decision Primitives

| Primitive | Output Type | Representation | Example Decision Question |
| :--- | :--- | :--- | :--- |
| **`bool`** | Binary boolean | `true` / `false` + confidence | *"Does claim B supersede or negate claim A?"* |
| **`choice`** | Discrete enum | `selection` from candidate set | *"Which worker lane should run: A, B, or C?"* |
| **`score`** | Continuous scalar | Float in `[0.0000, 1.0000]` | *"Urgency / quality score from 0 to 1"* |
| **`composite`** | Typed decision card | `{gate: bool, action: choice, score: float}` | Single-shot triage card combining all 3 primitives |

---

## 🛠️ CLI Quickstart

```bash
JEV="python3 /run/media/rodri/AI/skills/jev-decision/jev_decision.py"

# 1. Binary Decision (Bool)
$JEV bool --context "Postgres was deprecated and replaced with SQLite." \
          --question "Does SQLite supersede Postgres?"
# Output: ⚖️ [JEV Bool] -> YES (Confidence: 92.0%) [onejev_1.5_4b_server]

# 2. Constrained Enum Selection (Choice)
$JEV choice --context "Integration tests must run in parallel across 16 CPU cores." \
            --question "Which runner lane?" \
            --options sequential_lane parallel_worker_lane skip_tests
# Output: 🎯 [JEV Choice] -> 'parallel_worker_lane' (Confidence: 89.5%) [onejev_1.5_4b_server]

# 3. Scalar Magnitude Score (Score)
$JEV score --context "Unit tests achieve 100% coverage with zero failures." \
           --criteria "test coverage and zero failures"
# Output: 📊 [JEV Score] -> 1.0000 / 1.0000 [onejev_1.5_4b_server]

# 4. Composite Decision Card (Single-Shot Triage)
$JEV composite --context "Refactored test suite with 100% pass rate." \
               --question "Is this pull request safe and high quality?" \
               --options merge_now request_changes block --json

# 5. Multimodal Vision Decision (--image)
$JEV bool --context "Visual screen inspection of order page." \
          --question "Is order confirmation banner visible?" \
          --image /path/to/screenshot.png

# 6. Pairwise Context Cleaning & De-duplication
$JEV clean-context --claims-file claims.json

# 7. Frontend Visual UAT Action Selection (<500ms)
$JEV uat --intent "Click the checkout button" --dom-file dom_elements.json --image screen.png

# 8. Remote Fleet & Tailscale Execution
# Automatic Base64 inlining for images; works from laptop over Tailscale HTTPS:
export JEV_HOST="rodri-x870-taichi-creator.tail2975a8.ts.net"
jev-decision bool --context "Cluster health check" --question "Is network healthy?"
jev-decision bool --context "Inspection" --question "Is banner visible?" --image /path/to/local/screenshot.png
```
