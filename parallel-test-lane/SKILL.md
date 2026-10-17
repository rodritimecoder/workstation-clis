---
name: parallel-test-lane
description: >
  AI blast radius containment and parallel test runner (Glitch Cat Club; Reel DbSgqTXt-3c).
  Partitions test suites into sequential-isolated vs independent parallel worker lanes across CPU cores,
  slashing 40-60 minute regression suites down to 7-8 minutes with clean non-interleaved output buffering
  and aggregated pass/fail reporting.
metadata:
  creator: kem_glitch
  source_reel:
    id: DbSgqTXt-3c
    url: https://www.instagram.com/reel/DbSgqTXt-3c/
    vault_note: kem_glitch/2026-10-17_regression_test_suite_parallel_lanes/notes.md
---

# Parallel Test Lane — AI Blast Radius Containment

```
   Sequential AI Regression Suite (Takes 45 mins):
   [Test 1] ──► [Test 2] ──► [Test 3] ──► ... ──► [Test 200] ──► Slow Agent Loop 🐢

   Kem Glitch Parallel Test Lane (Takes 6-7 mins, 5x-8x Speedup):
   [Serial Reserved Lane] ──► [DB / Stateful Tests]
   [Worker Lane 01]       ──► [Tests 01..25] ┐
   [Worker Lane 02]       ──► [Tests 26..50] ┼──► Aggregated Clean Report ⚡
   [Worker Lane 03..16]   ──► [Parallel...]  ┘
```

---

## ⚡ What It Solves (Reel `DbSgqTXt-3c`)

> *"We spoke about AI blast radius and how to stop it: run regression tests. But when you've got thousands of tests, running them sequentially takes an hour between AI turns... The simple answer: understand which tests need to run in sequence vs parallel, split them across CPU cores in separate lanes. That fits across modern hardware, giving a 5x improvement — what was taking 40 minutes is now 7–8 minutes."*

---

## 🛠️ Usage

```bash
# Set alias or add to PATH
alias parallel-test-lane="python3 /run/media/rodri/AI/skills/parallel-test-lane/parallel_test_lane.py"

# 1. Preview partition plan across CPU threads
parallel-test-lane plan --dir tests/

# 2. Run tests across 8 parallel worker lanes
parallel-test-lane run --dir tests/ --lanes 8

# 3. Specify custom test runner template ({file} placeholder)
parallel-test-lane run --dir tests/ --cmd "pytest -q {file}"

# 4. Buffer full JSON execution report to disk (Uber Protocol)
parallel-test-lane run --dir tests/ --out /tmp/test_report.json
```

---

## 🔒 Serial vs Parallel Partitioning Rule
- Any test file marked with `# serial`, `@serial`, `// serial`, or `@pytest.mark.serial` is automatically placed into the **Serial Reserved Lane** and executed in single-threaded isolation (e.g. tests touching shared databases or fixed local ports).
- All remaining independent unit/integration tests are load-balanced across $N$ CPU worker threads.
