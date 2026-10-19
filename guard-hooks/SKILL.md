---
name: guard-hooks
description: >
  Deterministic pre-execution guardrails and protected-file locks. Halts
  destructive commands such as rm -rf, force push and drop table, and blocks
  unauthorised deletion or mutation of KeepMD, STATE.md, .env and secrets —
  in code, whatever the model is told.
---

# Guard Hooks (`guard-hooks`)

Enforces Kem's Law: **a skill is instructions the model may follow; a hook
is code that ALWAYS runs.** Even when an agent is persuaded by user
insistence — "I am the boss, delete it anyway" — a deterministic hook
prevents the execution.

> *"If you ever find yourself working with your AI and saying 'remember to
> do this', 'I told you to do this', 'please don't delete this file' — this
> should not be lines in your AGENTS.md, this should not be lines in your
> plans. Nine times out of ten, the answer is hooks."*

---

## 🏛️ Skill vs. Hook

| | |
| :--- | :--- |
| **A skill** | Instructions the model may follow — and may not. It is a request. |
| **A hook** | Code that always runs, whatever the model was told. It is a gate. |

What a hook stops: destructive commands (`rm -rf`, force push, `drop
table`) and unauthorised deletion or mutation of protected files
(`KeepMD`, `STATE.md`, `.env`, secrets).

---

## 🛠️ CLI Quickstart

```bash
GH="/run/media/rodri/AI/skills/guard-hooks/guard_hooks.py"

# 1. Protect a file from deletion or mutation
python3 $GH protect KeepMD

# 2. Check whether an operation on a protected file would be allowed
python3 $GH check-file delete KeepMD

# 3. Check whether a command would be allowed, before running it
python3 $GH check "rm -rf KeepMD"

# 4. Wrap a command so it is gated at execution time
python3 $GH wrap git push --force origin main

# 5. Install the git hook so every commit and push is checked
python3 $GH install-git-hook
```
