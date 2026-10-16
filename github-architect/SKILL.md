---
name: github-architect
description: "Autonomous GitHub repository architect, synchronizer, and multi-machine bootstrapper. Features disciplined 6-stage git branch synchronization (git-sync: Look, Guard, Commit, Gate, Pull, Push, Report), fleet-wide status and rebase sync, secret & blob shielding, and zero-drift environment onboarding."
---

# GitHub Architect (`github-architect`)

An autonomous, zero-friction tool for turning local workspaces into clean, well-documented, and secret-shielded GitHub repositories, synchronizing fleets of repositories across machines, and bootstrapping entire agent workstations without physical drives.

By default, **all created repositories are strictly PRIVATE** to protect proprietary code, notes, and local scripts.

---

## 🚀 Quick Usage

Executable directly or via Python:

```bash
# 1. Disciplined 6-Stage Branch Synchronization (git-sync protocol)
git-sync [-m "commit message"] [-y] [--dry-run] [--no-pull] [--no-gate] [--table] [--json]
# Or via github-architect:
github-architect git-sync [-m "commit message"] [-y] [--dry-run] [--table] [--json]

# 2. Fleet Dashboard: Inspect all workstation repositories at a glance
github-architect status-all [--table] [--json] [--project repository branch worktree remote_sync] [--limit 5]

# 3. Fleet Sync: Pull rebase, commit local changes, and push across ALL fleet repositories
github-architect sync-all [-m "sync fleet updates"]

# 4. Single Repository Audit (git status, auth, secret scanning, oversized blob guard)
github-architect audit [path] [--table] [--json]

# 5. Single Repository Sync (pull rebase + auto-commit + push)
github-architect sync [path] [-m "commit message"]

# 6. Scaffold documentation, .gitignore, and LICENSE without committing
github-architect scaffold [path] [--name repo-name]

# 7. Publish to GitHub (strictly PRIVATE by default; supports --template and --public)
github-architect publish [path] [--name repo-name] [--template] [--public]

# 8. Bootstrap complete agent environment on a new machine from GitHub
github-architect bootstrap [--dest ~/workspace]

# 9. Clone any GitHub repository via gh CLI
github-architect clone <repo-name> [dest]
```

---

## 🛡️ Core Capabilities & Multi-Machine Portability

1. **Disciplined 6-Stage Branch Synchronization (`git-sync`)**:
   - **Stage 1 (Look)**: Validates current branch, upstream tracking, active rebase/merge locks, and uncommitted changes.
   - **Stage 2 (Guard)**: Scans every dirty file against deterministic secret patterns (`ghp_*`, `sk-*`, `AIza*`, private keys, `.env`, `credentials.json`) and blocks files `>50 MB`.
   - **Stage 3 (Commit)**: Stages ONLY validated files explicitly (never blanket `git add -A`), generating conventional summaries.
   - **Stage 4 (Gate)**: Auto-detects and executes project quality gates (`npm test`, `pytest`, `cargo test`, `go test`) prior to pushing.
   - **Stage 5 (Pull)**: Safe merge pull (`--no-rebase`) preserving local commit topology.
   - **Stage 6 (Push)**: Pushes upstream with interactive prompt confirmation before touching protected default branches (`main`/`master`), overrideable with `-y`.
   - **Stage 7 (Report)**: Emits a structured 5-line receipt showing commits, pull/push status, and any left-out files.

2. **Fleet-Wide Synchronization (`status-all` & `sync-all`)**:
   - Manages all 5 core workstation repositories (`my-agent-skills`, `workstation-clis`, `academic-agent-skills`, `agent-multiplayer-template`, `university`).
   - One-command rebase, dirty-tree check, commit, and push across your entire machine.
   - Automatically runs `sync-skills` whenever the skills repository is synced.

3. **Grounded Secret & Large-Blob Guard**:
   - Actively checks git diffs before committing or pushing for secret tokens (`ghp_*`, `sk-*`, `AIza*`, private keys).
   - Blocks accidental commits of files `>50 MB` (preventing push rejections from heavy model weights, SQLite databases, or videos).
   - Override with `--force` when intentional.

4. **Single-Command Workstation Onboarding (`bootstrap`)**:
   - Zero physical drive requirement.
   - Clones and links the entire 5-repository workstation suite.
   - Sets up symlinks in `~/.local/bin/` and propagates all skills directly into `~/.gemini/config/skills/`.

5. **GitHub Template Support (`publish --template`)**:
   - Creates reusable GitHub Template repositories via direct GitHub API integration.

6. **Self-Healing Git Identity**:
   - Auto-detects GitHub username and handles missing `git config user.name` / `user.email` dynamically without failing operations.
