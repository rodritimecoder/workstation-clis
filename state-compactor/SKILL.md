---
name: state-compactor
description: >
  Autonomous state-file compaction harness for long agent loops and subagent handoffs
  (Kem Glitch / Glitch Cat Club architecture). Replaces lossy LLM summarizers and context rot
  with a live structured state ledger (.agent_state.json and STATE.md) updated while the agent
  is sharp. Triggers deterministic early compaction at customizable token thresholds, preserving
  100% of facts across 660,000+ token sessions without context poisoning.
---

# State Compactor — Zero-Degradation Long Context Protocol

```
   Traditional LLM Compaction (Lossy & Toxic):
   [Chat History (80k tokens)] ──► LLM Summarizer ──► [Hallucinated/Degraded Summary] ──► Context Poisoning

   Kem Glitch State Protocol (Zero-Loss):
   [Agent Execution] ──────────► Continuous Write to .agent_state.json while sharp
                                        │
   [Compaction Threshold Hit] ──────────▼
   [Fresh Context Window]    ◄── Inject Structured State File (100% Fact Parity)
```

---

## ⚡ Why This Exists (Reel `DdyqnietB8C`)

1. **Context Rot:** As conversations grow, token costs explode and model reasoning degrades.
2. **Context Poisoning:** Native auto-compaction triggers too late, runs an uncontrollable LLM summary over past turns, compresses an early hallucination or error into "truth", and infects all subsequent turns.
3. **The State File Solution:** Write facts, invariants, and decisions into a structured file (`.agent_state.json` / `STATE.md`) as work happens. When compacting, the context is reset and the state file is injected directly.

---

## 🛠️ Usage

```bash
# 1. Initialize in the current workspace
state-compactor init --goal "Build distributed Raft engine" --limit 30000

# 2. Record facts and decisions as you execute
state-compactor record --fact "Genesis 35B runs on :8080"
state-compactor record --decision "Use SQLite over Redis for zero dependencies"
state-compactor record --task "Add snapshotting unit tests"
state-compactor record --done "Scaffold Raft state machine"

# 3. Check compaction threshold (automated or agent turn)
state-compactor check

# 4. Generate clean zero-loss handover prompt
state-compactor compact --out /tmp/handover_prompt.md

# 5. Inspect current state ledger
state-compactor inspect
```
