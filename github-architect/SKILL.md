---
name: github-architect
description: Autonomous GitHub repository architect, synchronizer, and multi-machine bootstrapper. Audits local directories, generates secret-shielded .gitignore files, writes professional READMEs with skill catalogs, syncs changes across computers with rebase and conflict shielding, configures private licenses, and bootstraps complete agent environments via the GitHub CLI.
---

# GitHub Architect (`github-architect`)

An autonomous, zero-friction tool for turning local workspaces into clean, well-documented, and secret-shielded GitHub repositories, synchronizing fleets of repositories across machines, and bootstrapping entire agent workstations without physical drives.

By default, **all created repositories are strictly PRIVATE** to protect proprietary code, notes, and local scripts.

---

## 🚀 Quick Usage

Executable directly or via Python:

```bash
# 1. Fleet Dashboard: Inspect all workstation repositories at a glance
github-architect status-all

# 2. Fleet Sync: Pull rebase, commit local changes, and push across ALL fleet repositories
github-architect sync-all [-m "sync fleet updates"]

# 3. Single Repository Audit (git status, auth, secret scanning, oversized blob guard)
github-architect audit [path]

# 4. Single Repository Sync (pull rebase + auto-commit + push)
github-architect sync [path] [-m "commit message"]

# 5. Scaffold documentation, .gitignore, and LICENSE without committing
github-architect scaffold [path] [--name repo-name]

# 6. Publish to GitHub (strictly PRIVATE by default; supports --template and --public)
github-architect publish [path] [--name repo-name] [--template] [--public]

# 7. Bootstrap complete agent environment on a new machine from GitHub
github-architect bootstrap [--dest ~/workspace]

# 8. Clone any GitHub repository via gh CLI
github-architect clone <repo-name> [dest]
```

---

## 🛡️ Core Capabilities & Multi-Machine Portability

1. **Fleet-Wide Synchronization (`status-all` & `sync-all`)**:
   - Manages all 5 core workstation repositories (`my-agent-skills`, `workstation-clis`, `academic-agent-skills`, `agent-multiplayer-template`, `university`).
   - One-command rebase, dirty-tree check, commit, and push across your entire machine.
   - Automatically runs `sync-skills` whenever the skills repository is synced.

2. **Grounded Secret & Large-Blob Guard**:
   - Actively checks git diffs before committing or pushing for secret tokens (`ghp_*`, `sk-*`, `AIza*`, private keys).
   - Blocks accidental commits of files `>50 MB` (preventing push rejections from heavy model weights, SQLite databases, or videos).
   - Override with `--force` when intentional.

3. **Single-Command Workstation Onboarding (`bootstrap`)**:
   - Zero physical drive requirement.
   - Clones and links the entire 5-repository workstation suite.
   - Sets up symlinks in `~/.local/bin/` and propagates all skills directly into `~/.gemini/config/skills/`.

4. **GitHub Template Support (`publish --template`)**:
   - Creates reusable GitHub Template repositories via direct GitHub API integration.

5. **Self-Healing Git Identity**:
   - Auto-detects GitHub username and handles missing `git config user.name` / `user.email` dynamically without failing operations.
