---
name: worktree-harness
description: >
  Autonomous multi-agent Git worktree orchestration and quality gate harness (Glitch Cat Club;
  Reel DeZUVT1t5vQ). Spawns N parallel subagents into isolated git worktrees on dedicated branches,
  enforces pre-write section claims (claims.json), validates deterministic code quality gates
  (code decides wherever it can), automates merge conflict arbitration with Jev, and maintains
  an immutable time-indexed event log.
metadata:
  creator: kem_glitch
  source_reel:
    id: DeZUVT1t5vQ
    url: https://www.instagram.com/reel/DeZUVT1t5vQ/
    vault_note: kem_glitch/2026-10-16_5_agents_writing_same_file_worktree/notes.md
---

# Worktree Harness — Multi-Agent Parallel Orchestration (`worktree-harness`)

`worktree-harness` is an autonomous multi-agent orchestration harness designed for high-concurrency coding tasks without file-clobbering. It implements the architecture detailed by Kem (Glitch Cat Club) and Anthropic's parallel subagent compiler workflows.

---

## 🏛️ The 5 Core Invariants

1. **Git Worktree Isolation**: Never let multiple subagents write to the same disk directory concurrently. Each worker runs in its own isolated worktree (`.harness/runs/<run_id>/worktrees/<worker>/`) on a dedicated branch.
2. **Pre-Write Section Claiming**: Agents declare and reserve file or line ranges in `claims.json` before writing, preventing overlapping collision.
3. **Deterministic Quality Gates ("Code Decides")**: Code and test suites decide whether work passes—models only judge when strictly necessary.
4. **Automated Merge Conflict Arbitration**: If two worker branches touch conflicting lines, an arbitrator agent (or local Jev decision model) synthesizes an additive resolution, followed immediately by automated test execution.
5. **Immutable Time-Indexed Event Log**: Every spawn, claim, gate pass/fail, and merge is recorded in `.harness/runs/<run_id>/events.jsonl`, enabling deterministic state replays.

---

## 🚀 CLI Commands

```bash
HARNESS=~/.gemini/config/skills/worktree-harness/scripts/harness.py
```

### 1. Initialize a Run and Spawn Isolated Worktrees
```bash
python3 $HARNESS start \
  --goal "Refactor API error handling and write integration tests" \
  --workers agent-auth agent-db agent-api \
  --run-name run_v1
```

### 2. Pre-Write Section Claiming
```bash
# Reserve a specific file/section before writing
python3 $HARNESS claim --run-id run_v1 --worker agent-auth --file "src/auth.py" --lines "1-50"
```

### 3. Run Quality Gates inside Worker Worktree
```bash
# Code decides: tests must pass before branch can be queued for integration
python3 $HARNESS gate --run-id run_v1 --worker agent-auth --test "pytest tests/test_auth.py"
```

### 4. Integrate Verified Branches with Automated Conflict Arbitration
```bash
# Sequentially merges passing branches into harness/run_v1/integration with global test validation
python3 $HARNESS integrate --run-id run_v1 --test "pytest"
```

### 5. Check Live Status & Claims Dashboard
```bash
python3 $HARNESS status --run-id run_v1
# Or structured JSON
python3 $HARNESS status --run-id run_v1 --json
```

### 6. Clean Teardown
```bash
# Safely removes worktrees while keeping the consolidated integration branch and event log
python3 $HARNESS teardown --run-id run_v1 --delete-branches
```

### 7. Autonomous 1-Command Swarm Compiler (`swarm-dispatch`)
Pairs `worktree-harness` with `openrouter-free` to spawn N parallel subagents in isolated worktrees, enforce section claims, run test quality gates, and automatically integrate passing branches:

```bash
# Via structured plan (tasks.json)
swarm-dispatch --tasks tasks.json

# Or direct CLI prompt
swarm-dispatch \
  --goal "Refactor user authentication and database models" \
  --workers wt-auth wt-db wt-api \
  --test "pytest" \
  --model "gemini-3.5-flash-lite"
```

