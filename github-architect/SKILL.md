---
name: github-architect

description: >
  Synchronize, audit, and bootstrap GitHub repositories across a fleet of
  machines. Disciplined git-sync protocol (Look, Guard, Commit, Gate, Pull,
  Push, Report), secret and blob shielding, and zero-drive workstation
  onboarding.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires git and an authenticated GitHub CLI."
metadata:
  author: "rodri"
allowed-tools: "Bash(git:*) Bash(gh:*) Bash(github-architect:*) Read Write"
---

# GitHub Architect (`github-architect`)

Turns local workspaces into clean, secret-shielded GitHub repositories,
synchronizes a fleet of repositories across machines, and bootstraps a whole
agent workstation from GitHub with no physical drive. Repositories it creates
are **strictly private** by default.

---

## 🏛️ The Git-Sync Protocol

| Stage | What it does | What it prevents |
| :--- | :--- | :--- |
| **Look** | Validates branch, upstream tracking, rebase/merge locks, uncommitted changes | Pushing from a broken state |
| **Guard** | Scans dirty files for secret patterns (`ghp_*`, `sk-*`, `AIza*`, private keys, `.env`) and blocks files over 50 MB | Leaking a token, or a rejected push |
| **Commit** | Stages only validated files, explicitly — never a blanket `git add -A` | Sweeping an unrelated file into the commit |
| **Gate** | Detects and runs the project's own quality gate (`npm test`, `pytest`, `cargo test`, `go test`) | Pushing code that does not pass |
| **Pull** | Safe merge pull (`--no-rebase`), preserving local commit topology | Rewriting published history |
| **Push** | Pushes upstream, confirming before touching a protected default branch (`main`/`master`); `-y` overrides | Force-pushing over someone else's work |
| **Report** | Emits a 5-line receipt: commits, pull/push status, files left out | Not knowing what actually happened |

---

## 🛠️ CLI Quickstart

```bash
# 1. Disciplined branch synchronization
git-sync [-m "commit message"] [-y] [--dry-run] [--no-pull] [--no-gate] [--table] [--json]

# 2. Fleet dashboard — every workstation repository at a glance
github-architect status-all [--table] [--json] [--project repository branch worktree remote_sync] [--limit 5]

# 3. Fleet sync — pull rebase, commit, and push across every repository
github-architect sync-all [-m "sync fleet updates"]

# 4. Audit one repository — status, auth, secret scan, oversized blob guard
github-architect audit [path] [--table] [--json]

# 5. Sync one repository — pull rebase, auto-commit, push
github-architect sync [path] [-m "commit message"]

# 6. Scaffold documentation, .gitignore, and LICENSE without committing
github-architect scaffold [path] [--name repo-name]

# 7. Publish to GitHub — private by default; --template, --public
github-architect publish [path] [--name repo-name] [--template] [--public]

# 8. Bootstrap a whole agent environment on a new machine
github-architect bootstrap [--dest ~/workspace]

# 9. Clone any GitHub repository via the gh CLI
github-architect clone <repo-name> [dest]
```

---

## Reference

- `references/capabilities.md` — fleet sync, secret guard, onboarding, templates, git identity
