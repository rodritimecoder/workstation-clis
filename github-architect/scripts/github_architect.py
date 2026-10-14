#!/usr/bin/env python3
"""
github_architect.py — Automated GitHub Repository Scaffolding, Auditing, Fleet Syncing & Multi-Machine Bootstrapping

Zero-dependency CLI tool for inspecting local project folders, generating tailored
.gitignore, LICENSE, and README.md files, syncing changes across machines,
scanning for secrets and large blobs, and managing fleet repositories via the GitHub CLI.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

DEFAULT_GITIGNORE = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual Environments
.venv/
venv/
env/
ENV/
.env/
.agent-reach-venv/
container-site-packages/

# Package & Distribution
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Heavy Model Weights & Blobs (Keep out of Git)
*.gguf
*.bin
*.pt
*.safetensors
*.onnx

# SQLite Databases & Storage
*.db
*.sqlite
*.sqlite3
rag.db

# C / C++ build outputs
*.o
*.obj
*.d
*.a
*.lib
*.so
*.dylib
*.exe
*.out

# Node / Web
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Secret & Environmental Credentials
.env
.env.local
.env.*.local
.homelab_litellm.env
*.pem
*.key
*.p12
*.pfx
id_rsa*
id_ed25519*

# Operating System & Editors
.DS_Store
Thumbs.db
.idea/
.vscode/*
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
*.swp
*.swo
*~
.Trash-*

# Sensitive Course Modules & Local Vaults
university-notes/
"""

DEFAULT_MIT_LICENSE = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

DEFAULT_PRIVATE_LICENSE = """All Rights Reserved.

Copyright (c) {year} {author}

This source code and related assets are private and confidential. Unauthorized copying,
transferring, distribution, or reproduction of this repository or any part thereof,
via any medium, is strictly prohibited without prior written permission from the owner.
"""

CORE_REPOSITORIES = [
    {
        "name": "my-agent-skills",
        "target": "skills",
        "description": "Canonical upstream repository of reusable agent skills & ICM workflows",
    },
    {
        "name": "workstation-clis",
        "target": "workstation-clis",
        "description": "Curated workstation engineering, sandbox, and local inference CLIs",
    },
    {
        "name": "academic-agent-skills",
        "target": "academic-agent-skills",
        "description": "Academic ICM, Canvas LMS, and Cornell active-recall tools",
    },
    {
        "name": "agent-multiplayer-template",
        "target": "agent-multiplayer-template",
        "description": "Multiplayer cloud workspace & homelab GPU template",
    },
    {
        "name": "university",
        "target": "University",
        "description": "University course materials, notes, and Knowledge Cosmos",
    },
]

SECRET_PATTERNS = [
    (re.compile(r"ghp_[A-Za-z0-9_]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "GitHub Fine-Grained Token"),
    (re.compile(r"sk-[a-zA-Z0-9-]{20,}"), "OpenAI / LiteLLM Secret Key"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google API Key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private Key Block"),
]

MAX_BLOB_SIZE_MB = 50.0

FLEET_SEARCH_PATHS = [
    Path("/run/media/rodri/AI"),
    Path.home() / "workspace",
    Path.home(),
]


def run_cmd(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed (exit {res.returncode}): {cmd}\nStderr: {res.stderr.strip()}")
    return res


def check_gh_status() -> Tuple[bool, str]:
    res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if res.returncode != 0:
        return False, ""
    user_res = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True)
    user = user_res.stdout.strip() if user_res.returncode == 0 else ""
    return True, user


def ensure_git_identity() -> Tuple[str, str]:
    name = run_cmd("git config user.name", check=False).stdout.strip()
    email = run_cmd("git config user.email", check=False).stdout.strip()

    if not name or not email:
        is_auth, gh_user = check_gh_status()
        if is_auth and gh_user:
            if not name:
                name = gh_user
                run_cmd(f'git config --global user.name "{name}"', check=False)
                print(f"  🔧 Auto-configured git user.name: {name}")
            if not email:
                email = f"{gh_user}@users.noreply.github.com"
                run_cmd(f'git config --global user.email "{email}"', check=False)
                print(f"  🔧 Auto-configured git user.email: {email}")
        else:
            name = name or "rodritimecoder"
            email = email or "rodritimecoder@users.noreply.github.com"

    return name, email


def check_secrets_and_blobs(repo_path: Path, staged_only: bool = True) -> Tuple[List[str], List[str]]:
    secret_hits: List[str] = []
    blob_hits: List[str] = []

    diff_files_cmd = ["git", "diff", "--name-only", "--cached"] if staged_only else ["git", "status", "--porcelain"]
    res = run_cmd(diff_files_cmd, cwd=repo_path, check=False)
    lines = res.stdout.strip().splitlines()

    for line in lines:
        fname = line.strip().split()[-1] if not staged_only else line.strip()
        p = repo_path / fname
        if p.is_file():
            try:
                size_mb = p.stat().st_size / (1024 * 1024)
                if size_mb > MAX_BLOB_SIZE_MB:
                    blob_hits.append(f"{p.relative_to(repo_path)} ({size_mb:.1f} MB > {MAX_BLOB_SIZE_MB} MB limit)")
            except Exception:
                pass

    diff_text_cmd = ["git", "diff", "--cached"] if staged_only else ["git", "diff"]
    diff_res = run_cmd(diff_text_cmd, cwd=repo_path, check=False)
    for line in diff_res.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added = line[1:]
            for pattern, label in SECRET_PATTERNS:
                m = pattern.search(added)
                if m:
                    token = m.group(0)
                    masked = token[:6] + "..." + token[-4:] if len(token) > 12 else "***"
                    secret_hits.append(f"{label}: {masked}")

    return secret_hits, blob_hits


def parse_skills_metadata(skills_dir: Path):
    skills = []
    for item in sorted(skills_dir.iterdir()):
        skill_md = item / "SKILL.md"
        if item.is_dir() and skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8")
            name = item.name
            desc = "Agent skill"
            match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
            if match:
                fm = match.group(1)
                name_m = re.search(r"^name:\s*([^\n]+)", fm, re.MULTILINE)
                if name_m:
                    name = name_m.group(1).strip()
                desc_m = re.search(r"^description:\s*([^\n]+)", fm, re.MULTILINE)
                if desc_m:
                    desc = desc_m.group(1).strip()
            skills.append({"dir": item.name, "name": name, "description": desc})
    return skills


def generate_skills_readme(target_path: Path, repo_name: str, author: str) -> str:
    skills = parse_skills_metadata(target_path)

    rows = []
    for s in skills:
        clean_desc = s["description"].split(".")[0] if "." in s["description"] else s["description"]
        clean_desc = clean_desc.replace("|", "\\|")[:90]
        rows.append(f"| [`{s['dir']}`]({s['dir']}/) | `{s['name']}` | {clean_desc} |")

    skills_table = "\n".join(rows)

    return f"""# {repo_name}

[![Private Repository](https://img.shields.io/badge/Repository-Private-red.svg)](https://github.com/{author}/{repo_name})
[![Skills Count](https://img.shields.io/badge/Skills-{len(skills)}-blue.svg)](#skills-catalog)
[![Upstream Canonical](https://img.shields.io/badge/Source-Upstream%20Canonical-success.svg)](#architecture)

> **Canonical upstream repository** of reusable AI agent skills, CLI automation tools, and ICM (Interpretable Context Methodology) workspaces on this machine.

---

## 🏛️ Architecture & Upstream-First Synchronization

This repository serves as the **single source of truth** across all local agent harnesses (`~/.gemini/config/skills` and `~/.pi/agent/skills`).

```
┌─────────────────────────────────────────────────────────────┐
│       Canonical Upstream Repository (This Repo)             │
│                /run/media/rodri/AI/skills                   │
└──────────────────────────────┬──────────────────────────────┘
                               │  sync-skills
                               ▼
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              ▼
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  Antigravity / Gemini CLI   │       │       Pi Agent CLI           │
│   ~/.gemini/config/skills/   │       │     ~/.pi/agent/skills/      │
└──────────────────────────────┘       └──────────────────────────────┘
```

Whenever updating, refactoring, or creating any skill:
1. Make file edits directly in this repository first.
2. Run `sync-skills` in the terminal to immediately propagate downstream without ephemeral `.venv` or cache bloat.

---

## 📦 Skills Catalog ({len(skills)} Skills)

| Skill Directory | Identifier | Core Capabilities |
| :--- | :--- | :--- |
{skills_table}

---

## 🚀 Quickstart & Usage

### 1. Synchronize to Local Agent Harnesses
To push updates from this repository to your active Antigravity and Pi harnesses:
```bash
sync-skills
```

### 2. Pull Downstream Edits (Parity Restore)
If a skill was modified downstream, pull changes back upstream with:
```bash
sync-skills --pull
```

---

## 🔒 License & Confidentiality
Private repository owned by {author}. Contains customized pipelines, academic integrations, and local inference tooling.
"""


def cmd_audit(target: Path):
    print(f"\n🔍 [Audit] Inspecting repository target: {target.resolve()}")
    if not target.is_dir():
        print(f"❌ Error: Target directory does not exist: {target}")
        return False

    has_git = (target / ".git").is_dir()
    has_gitignore = (target / ".gitignore").is_file()
    has_readme = (target / "README.md").is_file()
    has_license = (target / "LICENSE").is_file() or (target / "LICENSE.md").is_file()

    print(f"  • Git initialized:   {'✅ Yes' if has_git else '❌ Missing (.git folder)'}")
    print(f"  • .gitignore:        {'✅ Yes' if has_gitignore else '❌ Missing (.gitignore)'}")
    print(f"  • README.md:         {'✅ Yes' if has_readme else '❌ Missing (README.md)'}")
    print(f"  • LICENSE:           {'✅ Yes' if has_license else '❌ Missing (LICENSE)'}")

    is_auth, gh_user = check_gh_status()
    print(f"  • GitHub CLI Auth:   {'✅ Logged in (@' + gh_user + ')' if is_auth else '❌ Not logged in (run gh auth login)'}")

    git_user = run_cmd("git config user.name", check=False).stdout.strip()
    git_email = run_cmd("git config user.email", check=False).stdout.strip()
    if git_user and git_email:
        print(f"  • Git Identity:      ✅ {git_user} <{git_email}>")
    else:
        print(f"  • Git Identity:      ⚠️ Incomplete ({git_user or 'no user'} / {git_email or 'no email'})")

    if has_git:
        remotes = run_cmd("git remote -v", cwd=target, check=False).stdout.strip()
        print(f"  • Remote Origin:     {remotes.splitlines()[0] if remotes else '⚪ No remote configured'}")

        dirty = bool(run_cmd("git status --porcelain", cwd=target, check=False).stdout.strip())
        print(f"  • Working Tree:      {'⚠️ Uncommitted changes' if dirty else '✅ Clean'}")

        status_sb = run_cmd("git status -sb", cwd=target, check=False).stdout.strip().splitlines()
        if status_sb:
            print(f"  • Branch Tracking:   {status_sb[0]}")

        sec_hits, blob_hits = check_secrets_and_blobs(target, staged_only=False)
        if sec_hits:
            print(f"  • ⚠️  Secret Warnings: {len(sec_hits)} suspicious key patterns detected!")
            for s in sec_hits[:3]:
                print(f"       - {s}")
        else:
            print(f"  • Secret Scanner:    ✅ No uncommitted secrets detected")

        if blob_hits:
            print(f"  • ⚠️  Large Blobs:    {len(blob_hits)} files exceed {MAX_BLOB_SIZE_MB}MB limit!")
            for b in blob_hits[:3]:
                print(f"       - {b}")
        else:
            print(f"  • Large Blobs:       ✅ All files under {MAX_BLOB_SIZE_MB}MB")

    return True


def cmd_scaffold(target: Path, repo_name: str, private: bool = True, license_type: str = "private"):
    print(f"\n🛠️  [Scaffold] Building repository assets in: {target.resolve()}")
    target.mkdir(parents=True, exist_ok=True)

    gi_path = target / ".gitignore"
    if not gi_path.exists():
        gi_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print(f"  ✅ Created .gitignore (blocks .venv, __pycache__, build artifacts, models, secrets)")
    else:
        print(f"  ℹ️  .gitignore already exists (preserved)")

    lic_path = target / "LICENSE"
    author, _ = ensure_git_identity()
    year = "2026"
    if not lic_path.exists():
        if license_type.lower() == "mit":
            lic_content = DEFAULT_MIT_LICENSE.format(year=year, author=author)
        else:
            lic_content = DEFAULT_PRIVATE_LICENSE.format(year=year, author=author)
        lic_path.write_text(lic_content, encoding="utf-8")
        print(f"  ✅ Created LICENSE ({license_type.upper()})")
    else:
        print(f"  ℹ️  LICENSE already exists (preserved)")

    readme_path = target / "README.md"
    is_skills_repo = any((target / s / "SKILL.md").is_file() for s in target.iterdir() if s.is_dir())

    if is_skills_repo:
        readme_content = generate_skills_readme(target, repo_name, author)
        readme_path.write_text(readme_content, encoding="utf-8")
        print(f"  ✅ Generated enriched skills README.md with architecture flowchart & catalog table")
    elif not readme_path.exists():
        basic_readme = f"# {repo_name}\n\nPrivate repository managed by {author}.\n"
        readme_path.write_text(basic_readme, encoding="utf-8")
        print(f"  ✅ Generated base README.md")
    else:
        print(f"  ℹ️  README.md already exists (preserved)")


def cmd_publish(target: Path, repo_name: str, private: bool = True, license_type: str = "private", is_template: bool = False, force: bool = False):
    print(f"\n🚀 [Publish] Preparing and publishing {repo_name} to GitHub...")

    is_auth, user = check_gh_status()
    if not is_auth:
        print("❌ Error: GitHub CLI ('gh') is not authenticated. Run: gh auth login")
        return False

    ensure_git_identity()
    cmd_scaffold(target, repo_name, private=private, license_type=license_type)

    if not (target / ".git").is_dir():
        run_cmd(["git", "init", "-b", "main"], cwd=target)
        print("  ✅ Initialized local Git repository (branch: main)")

    sec_hits, blob_hits = check_secrets_and_blobs(target, staged_only=False)
    if (sec_hits or blob_hits) and not force:
        print("\n❌ Publishing ABORTED due to Grounded Security Guard:")
        for s in sec_hits:
            print(f"  ⚠️  Detected Secret: {s}")
        for b in blob_hits:
            print(f"  ⚠️  Detected Oversized Blob: {b}")
        print("\n💡 Pass '--force' if you explicitly intend to publish these files.")
        return False

    run_cmd(["git", "add", "."], cwd=target)
    status = run_cmd(["git", "status", "--porcelain"], cwd=target).stdout.strip()
    if status:
        run_cmd(["git", "commit", "-m", "feat: initial commit with github-architect scaffold"], cwd=target)
        print("  ✅ Committed all staged files")
    else:
        print("  ℹ️  No changes to commit (working tree clean)")

    remotes = run_cmd(["git", "remote"], cwd=target, check=False).stdout.strip().splitlines()
    visibility_flag = "--private" if private else "--public"

    if "origin" not in remotes:
        print(f"  🌐 Creating remote repository '{repo_name}' on GitHub ({visibility_flag})...")
        gh_cmd = ["gh", "repo", "create", repo_name, visibility_flag, "--source=.", "--remote=origin", "--push"]
        res = run_cmd(gh_cmd, cwd=target)
        print(f"  ✅ Successfully published to GitHub: {res.stdout.strip()}")
    else:
        print(f"  📤 Remote 'origin' already exists. Pulling latest and pushing to origin...")
        run_cmd(["git", "pull", "--rebase", "origin", "main"], cwd=target, check=False)
        run_cmd(["git", "push", "-u", "origin", "main"], cwd=target)
        print("  ✅ Pushed changes to existing remote origin")

    owner_repo = run_cmd(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], cwd=target, check=False).stdout.strip()
    repo_url = run_cmd(["gh", "repo", "view", "--json", "url", "--jq", ".url"], cwd=target, check=False).stdout.strip()

    if is_template and owner_repo:
        print(f"  🏷️  Configuring repository as a GitHub Template...")
        tpl_res = run_cmd(["gh", "api", "-X", "PATCH", f"repos/{owner_repo}", "-f", "is_template=true"], check=False)
        if tpl_res.returncode == 0:
            print("  ✅ Successfully marked as Template Repository!")

    vis_label = "Private" if private else "Public"
    print(f"\n🎉 Repository Live & Protected: {repo_url} ({vis_label}{', Template' if is_template else ''})")
    return True


def cmd_sync(target: Path, message: Optional[str] = None, force: bool = False) -> bool:
    print(f"\n🔄 [Sync] Synchronizing repository: {target.resolve()}")
    if not (target / ".git").is_dir():
        print(f"❌ Error: {target} is not a git repository.")
        return False

    ensure_git_identity()

    remotes = run_cmd(["git", "remote"], cwd=target, check=False).stdout.strip().splitlines()
    if "origin" not in remotes:
        print("❌ Error: No remote 'origin' configured.")
        return False

    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=target, check=False).stdout.strip() or "main"

    sec_hits, blob_hits = check_secrets_and_blobs(target, staged_only=False)
    if (sec_hits or blob_hits) and not force:
        print("\n❌ Sync ABORTED due to Grounded Security Guard:")
        for s in sec_hits:
            print(f"  ⚠️  Detected Secret: {s}")
        for b in blob_hits:
            print(f"  ⚠️  Detected Oversized Blob: {b}")
        print("\n💡 Pass '--force' if you explicitly intend to sync these files.")
        return False

    status = run_cmd(["git", "status", "--porcelain"], cwd=target, check=False).stdout.strip()
    if status:
        print("  📝 Local changes detected. Staging and committing...")
        run_cmd(["git", "add", "."], cwd=target)
        hostname = os.uname().nodename if hasattr(os, "uname") else "workstation"
        commit_msg = message or f"chore: sync updates from {hostname}"
        run_cmd(["git", "commit", "-m", commit_msg], cwd=target)
        print(f"  ✅ Committed local changes: '{commit_msg}'")
    else:
        print("  ℹ️  Working tree clean (no new local changes to commit).")

    print(f"  📥 Pulling remote changes from origin/{branch} (rebase)...")
    pull_res = run_cmd(["git", "pull", "--rebase", "origin", branch], cwd=target, check=False)
    if pull_res.returncode != 0:
        print(f"  ⚠️ Warning: Pull rebase had warnings/conflicts:\n{pull_res.stderr.strip()}")
    else:
        print(f"  ✅ Branch origin/{branch} rebased cleanly.")

    print(f"  📤 Pushing commits to origin/{branch}...")
    push_res = run_cmd(["git", "push", "origin", branch], cwd=target, check=False)
    if push_res.returncode == 0:
        print(f"  ✅ Successfully synchronized and pushed to origin/{branch}!")
    else:
        print(f"  ❌ Push failed:\n{push_res.stderr.strip()}")
        return False

    # Propagate skills if applicable
    if (target / "sync_skills.sh").is_file() or (target / "scripts" / "sync_skills.sh").is_file():
        sync_sh = target / "sync_skills.sh" if (target / "sync_skills.sh").is_file() else target / "scripts" / "sync_skills.sh"
        print("  🔄 Propagating skills to downstream CLI harnesses...")
        run_cmd(["bash", str(sync_sh)], cwd=target, check=False)

    return True


def discover_fleet_repos() -> List[Dict[str, Any]]:
    fleet = []
    seen_paths = set()

    for repo_def in CORE_REPOSITORIES:
        target_name = repo_def["target"]
        repo_name = repo_def["name"]
        found_path = None

        for base in FLEET_SEARCH_PATHS:
            cand = base / target_name
            if (cand / ".git").is_dir():
                found_path = cand
                break
            cand_alt = base / repo_name
            if (cand_alt / ".git").is_dir():
                found_path = cand_alt
                break

        if found_path and found_path.resolve() not in seen_paths:
            seen_paths.add(found_path.resolve())
            fleet.append({
                "name": repo_name,
                "path": found_path.resolve(),
                "description": repo_def["description"]
            })

    return fleet


def cmd_status_all() -> None:
    fleet = discover_fleet_repos()
    if not fleet:
        print("❌ No workstation fleet repositories found.")
        return

    print(f"\n🚢 [Fleet Status] Inspecting {len(fleet)} workstation repositories:\n")
    print(f"  {'Repository':<28} │ {'Branch':<8} │ {'Worktree':<10} │ {'Remote Sync':<15} │ Last Commit")
    print("  ─────────────────────────────┼──────────┼────────────┼─────────────────┼──────────────────────────────")

    for r in fleet:
        p = r["path"]
        branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=p, check=False).stdout.strip() or "main"
        dirty_lines = run_cmd(["git", "status", "--porcelain"], cwd=p, check=False).stdout.strip().splitlines()
        dirty_count = len(dirty_lines)
        if dirty_count > 0:
            worktree_str = f"\033[33m{dirty_count} dirty\033[0m"
        else:
            worktree_str = "\033[32mClean\033[0m"

        rev_res = run_cmd(["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"], cwd=p, check=False)
        if rev_res.returncode == 0:
            parts = rev_res.stdout.strip().split()
            ahead = int(parts[0]) if len(parts) > 0 else 0
            behind = int(parts[1]) if len(parts) > 1 else 0
            if ahead == 0 and behind == 0:
                sync_str = "\033[32mUp to date\033[0m"
            elif ahead > 0 and behind == 0:
                sync_str = f"\033[33mAhead ({ahead})\033[0m"
            elif ahead == 0 and behind > 0:
                sync_str = f"\033[31mBehind ({behind})\033[0m"
            else:
                sync_str = f"\033[35mDiverged (+{ahead}/-{behind})\033[0m"
        else:
            sync_str = "\033[90mNo upstream\033[0m"

        last_commit = run_cmd(["git", "log", "-1", "--format=%h (%cr) - %s"], cwd=p, check=False).stdout.strip()
        last_commit_short = last_commit[:40] + "..." if len(last_commit) > 40 else last_commit

        print(f"  {r['name']:<28} │ {branch:<8} │ {worktree_str:<19} │ {sync_str:<24} │ {last_commit_short}")
    print()


def cmd_sync_all(message: Optional[str] = None, force: bool = False) -> None:
    fleet = discover_fleet_repos()
    if not fleet:
        print("❌ No workstation fleet repositories found.")
        return

    print(f"\n🚀 [Fleet Sync] Synchronizing all {len(fleet)} workstation repositories...\n")
    success_count = 0
    for r in fleet:
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 Synchronizing: {r['name']} ({r['path']})")
        ok = cmd_sync(r["path"], message=message, force=force)
        if ok:
            success_count += 1

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🎉 Fleet Sync Complete: {success_count}/{len(fleet)} repositories synchronized cleanly.")


def cmd_clone(repo: str, dest: Optional[Path] = None):
    is_auth, user = check_gh_status()
    if not is_auth:
        print("❌ Error: GitHub CLI ('gh') is not authenticated. Run: gh auth login")
        return False

    repo_slug = repo if "/" in repo else f"{user}/{repo}"
    print(f"\n📦 [Clone] Cloning {repo_slug}...")
    cmd = ["gh", "repo", "clone", repo_slug]
    if dest:
        cmd.append(str(dest))
    res = run_cmd(cmd, check=False)
    if res.returncode == 0:
        print(f"  ✅ Successfully cloned {repo_slug}")
        return True
    else:
        print(f"  ❌ Clone failed: {res.stderr.strip()}")
        return False


def cmd_bootstrap(dest_dir: Optional[Path] = None):
    if dest_dir is None:
        ai_mount = Path("/run/media/rodri/AI")
        dest_dir = ai_mount if ai_mount.is_dir() else (Path.home() / "workspace")

    print(f"\n🚀 [Bootstrap] Setting up agent environment in: {dest_dir.resolve()}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    is_auth, user = check_gh_status()
    if not is_auth:
        print("❌ Error: GitHub CLI ('gh') is not authenticated. Run: gh auth login")
        return False
    print(f"  ✅ Authenticated as GitHub user: @{user}")

    ensure_git_identity()

    for repo in CORE_REPOSITORIES:
        repo_name = repo["name"]
        target_path = dest_dir / repo["target"]
        repo_slug = f"{user}/{repo_name}"

        if (target_path / ".git").is_dir():
            print(f"\n📦 Repository already exists at {target_path}. Synchronizing...")
            cmd_sync(target_path)
        else:
            print(f"\n📦 Cloning {repo_slug} -> {target_path}...")
            clone_cmd = ["gh", "repo", "clone", repo_slug, str(target_path)]
            res = run_cmd(clone_cmd, check=False)
            if res.returncode == 0:
                print(f"  ✅ Successfully cloned {repo_slug}")
            else:
                print(f"  ⚠️ Could not clone {repo_slug}: {res.stderr.strip()}")

    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)

    skills_dir = dest_dir / "skills"
    if not skills_dir.exists():
        skills_dir = dest_dir / "my-agent-skills"

    if skills_dir.is_dir():
        sync_script = skills_dir / "sync_skills.sh"
        if sync_script.is_file():
            sync_symlink = local_bin / "sync-skills"
            if sync_symlink.is_symlink() or sync_symlink.is_file():
                sync_symlink.unlink()
            sync_symlink.symlink_to(sync_script)
            sync_script.chmod(0o755)
            print(f"  ✅ Linked sync-skills -> {sync_symlink}")

        arch_script = skills_dir / "github-architect" / "scripts" / "github_architect.py"
        if arch_script.is_file():
            arch_symlink = local_bin / "github-architect"
            if arch_symlink.is_symlink() or arch_symlink.is_file():
                arch_symlink.unlink()
            arch_symlink.symlink_to(arch_script)
            arch_script.chmod(0o755)
            print(f"  ✅ Linked github-architect -> {arch_symlink}")

        if sync_script.is_file():
            print("\n🔄 Propagating skills into Antigravity & Pi harnesses...")
            run_cmd(["bash", str(sync_script)], cwd=skills_dir, check=False)

    print("\n🎉 Bootstrap Complete! All repositories cloned, skills linked, and tools configured.")
    return True


def cmd_insights(target_dir: Path):
    print(f"\n🧠 [Insights] Synthesizing machine model knowledge into docs/...")
    docs_dir = target_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    guide_path = docs_dir / "models_and_services.md"

    summary = """# Autonomous Workstation Model Directory & Rankings

Synthesized by `github-architect` from local GPU inference configs, launchers, and agent conversation transcripts.

---

## 🏛️ Local Inference Ports

| Port | Model / Engine | Launcher | Best Used For |
|---|---|---|---|
| `:8080` | **Qwen3.6-35B-A3B (Genesis Q4_0_ROCMFP4)** | `launchers/ttq_server.sh` | Complex reasoning, coding, uncensored generation |
| `:8081` | **Nemotron 3.5 ASR + Kokoro TTS** | `audio.cpp` server | Real-time speech-to-text (40 langs) + fast speech synthesis |
| `:8082` | **NaviDC-OCR (Q8_0 / Q5_K_M)** | `launchers/navidc-ocr.sh` | Dense scanned PDFs and papers |
| `:8083` | **Imajev-4B Decision Model** | `launchers/imajev-4b.sh` | Multimodal decision gating ($T=1.305$) |
| `:8084` | **CrispEmbed Scene Text OCR** | `launchers/crispembed-ocr.sh` | Real-world scene-text OCR (DBNet + PARSeq) |
| `:8085` | **LightOnOCR-3-1B** | `launchers/lighton-ocr.sh` | **Flagship Video & Slide OCR** (~16k t/s prefill, ~330 t/s gen) |
| `:8085` | **Jev-Style-Qwen3.5-2B** | `launchers/jev-style-2b.sh` | Text classification without vision projector |
| `:8086` | **Jina-Reranker-v2 Base** | `launchers/jina-reranker.sh` | Cross-encoder RAG reranking |
| `:8087` | **EmbeddingGemma-2** | `launchers/embeddinggemma-2.sh` | Text + Vision multimodal embeddings |
| `:8088` | **DeskForge-Qwen3.5-4B** | `launchers/deskforge-qwen.sh` | Visual GUI grounding & computer use |
| `:8090` | **JPT-4B Decision Engine** | `launchers/jpt-4b/start-jpt.sh` | High-speed System One decision gating |

---

## 🏆 Model Rankings by Task

- **Video & Slide OCR**: `LightOnOCR-3-1B` (#1) > `SmolDocling-256M` (#2) > `NaviDC-OCR` (#3) > `CrispEmbed` (#4)
- **Calibrated Decisions**: `Imajev-4B` (Vision + Text) & `JPT-4B` (Fast Loop)
- **Browser Visual Grounding**: `DeskForge-Qwen3.5-4B` (GUI coordinates)
- **Speech-to-Text**: `Nemotron-3.5-ASR` (Streaming RNNT on `:8081`)
"""
    guide_path.write_text(summary, encoding="utf-8")
    print(f"  ✅ Generated: {guide_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        prog="github-architect",
        description="github-architect — Automated GitHub repo builder, fleet syncer & publisher"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status-all
    subparsers.add_parser("status-all", help="Display real-time status across all workstation fleet repositories")

    # sync-all
    p_sync_all = subparsers.add_parser("sync-all", help="Synchronize and rebase all workstation fleet repositories in one command")
    p_sync_all.add_argument("-m", "--message", type=str, default=None, help="Optional commit message for dirty repos")
    p_sync_all.add_argument("--force", action="store_true", help="Bypass secret and oversized blob guards")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit local repo structure, files, git, secrets, and gh status")
    p_audit.add_argument("path", type=str, nargs="?", default=".", help="Target directory (default: current)")

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Generate .gitignore, LICENSE, and README.md")
    p_scaffold.add_argument("path", type=str, nargs="?", default=".", help="Target directory")
    p_scaffold.add_argument("--name", type=str, default=None, help="Repository name")
    p_scaffold.add_argument("--license", type=str, default="private", choices=["private", "mit"], help="License type")

    # publish
    p_publish = subparsers.add_parser("publish", help="Scaffold, commit, and push repository to GitHub")
    p_publish.add_argument("path", type=str, nargs="?", default=".", help="Target directory")
    p_publish.add_argument("--name", type=str, default=None, help="Repository name (defaults to folder name)")
    p_publish.add_argument("--public", action="store_true", help="Publish as public (default is PRIVATE)")
    p_publish.add_argument("--template", action="store_true", help="Mark repository as a reusable GitHub Template")
    p_publish.add_argument("--license", type=str, default="private", choices=["private", "mit"], help="License type")
    p_publish.add_argument("--force", action="store_true", help="Bypass secret and oversized blob guards")

    # sync
    p_sync = subparsers.add_parser("sync", help="Pull latest remote changes (rebase), commit local changes, and push")
    p_sync.add_argument("path", type=str, nargs="?", default=".", help="Target repository directory (default: current)")
    p_sync.add_argument("-m", "--message", type=str, default=None, help="Optional commit message")
    p_sync.add_argument("--force", action="store_true", help="Bypass secret and oversized blob guards")

    # clone
    p_clone = subparsers.add_parser("clone", help="Clone repository via gh CLI")
    p_clone.add_argument("repo", type=str, help="Repository name (e.g. university or username/university)")
    p_clone.add_argument("dest", type=str, nargs="?", default=None, help="Destination directory")

    # bootstrap
    p_boot = subparsers.add_parser("bootstrap", help="Clone and set up all workstation repos and skills on a new machine")
    p_boot.add_argument("--dest", type=str, default=None, help="Destination directory for repositories")

    # insights
    p_ins = subparsers.add_parser("insights", help="Scan machine transcripts and configs to generate model docs")
    p_ins.add_argument("path", type=str, nargs="?", default=".", help="Target directory")

    args = parser.parse_args()

    if args.command == "status-all":
        cmd_status_all()
        return

    if args.command == "sync-all":
        cmd_sync_all(message=args.message, force=args.force)
        return

    if args.command == "bootstrap":
        dest_path = Path(args.dest).resolve() if args.dest else None
        cmd_bootstrap(dest_path)
        return

    if args.command == "clone":
        dest_path = Path(args.dest).resolve() if args.dest else None
        cmd_clone(args.repo, dest_path)
        return

    target_path = Path(args.path).resolve()
    repo_name = getattr(args, "name", None) or target_path.name

    if args.command == "audit":
        cmd_audit(target_path)
    elif args.command == "scaffold":
        cmd_scaffold(target_path, repo_name, private=True, license_type=args.license)
    elif args.command == "publish":
        cmd_publish(target_path, repo_name, private=not args.public, license_type=args.license, is_template=args.template, force=args.force)
    elif args.command == "sync":
        cmd_sync(target_path, message=getattr(args, "message", None), force=args.force)
    elif args.command == "insights":
        cmd_insights(target_path)


if __name__ == "__main__":
    main()
