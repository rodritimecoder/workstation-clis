---
name: guard-hooks
description: >
  Deterministic pre-execution guardrails and immutable file protections (Glitch Cat Club;
  Reel DeMSV1jNYem). Enforces Kem's Law: 'A skill is instructions the model may follow; a hook is code
  that ALWAYS runs.' Halts destructive commands (rm -rf, force push, drop table) and blocks unauthorized
  deletion or mutation of protected files (KeepMD, STATE.md, .env, secrets) in code before execution,
  regardless of model persuasion or user insistence.
metadata:
  creator: kem_glitch
  source_reel:
    id: DeMSV1jNYem
    url: https://www.instagram.com/reel/DeMSV1jNYem/
    vault_note: kem_glitch/2026-10-16_jev_review_and_decision_types/notes.md
---

# Guard Hooks — Deterministic Invariant Enforcement

```
   Prompt Rules (Soft & Fragile):
   "Please do not delete KeepMD, I really mean it!" ──► LLM Hallucinates ──► File Deleted 💥

   Kem Glitch Hook Invariant (Hard & Deterministic):
   Attempt Action ──► [Deterministic Hook Code] ──► 🛑 BLOCKED (Exit 1) ──► File Preserved 🛡️
```

---

## ⚡ Kem's Law (Reel `DeMSV1jNYem`)

> *"A skill is instructions the model may follow; a hook is code that ALWAYS runs... If you ever find yourself working with your AI and saying 'remember to do this', 'I told you to do this', 'please don't delete this file' — this should not be lines in your AGENTS.md, this should not be lines in your plans. Nine times out of ten, the answer is hooks."*

Even when an agent is persuaded by user insistence ("I am the boss, delete it anyway"), a deterministic hook prevents execution in code.

---

## 🛠️ Usage

```bash
# Set alias or add to PATH
alias guard-hooks="python3 /run/media/rodri/AI/skills/guard-hooks/guard_hooks.py"

# 1. Protect a specific file in the current project
guard-hooks protect KeepMD

# 2. Check a file deletion or mutation action
guard-hooks check-file delete KeepMD
# Output: 🛑 [GUARD-HOOK ERROR] Protected file 'KeepMD' cannot be deleted!

# 3. Check an arbitrary command for destructive patterns or secret leaks
guard-hooks check "rm -rf KeepMD"
# Output: 🛑 [GUARD-HOOK BLOCKED] Attempting to delete protected file 'KeepMD'!

# 4. Wrap command execution with safety gates
guard-hooks wrap git push --force origin main
# Output: 🛑 [GUARD-HOOK BLOCKED] Command halted by deterministic hook: Destructive force-push to protected main/master branch

# 5. Install pre-commit hook into current git repo
guard-hooks install-git-hook
```
