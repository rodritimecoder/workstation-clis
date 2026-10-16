#!/usr/bin/env python3
"""
git_sync.py — Disciplined 6-Stage Git Branch Synchronization Engine
Adapted from EricTechPro/super-board git-sync specification with deterministic security gates.

Stages:
  1. Look    - Verify working tree, upstream tracking, ahead/behind status.
  2. Guard   - Shield secrets (.env, keys, API tokens) and oversized blobs (>50MB).
  3. Commit  - Atomic path-specific staging (never 'git add -A').
  4. Gate    - Auto-discover & run fast repository checks (lint/typecheck/tests).
  5. Pull    - Safe merge pull (--no-rebase) with conflict shielding.
  6. Push    - Safe non-force push (with protected branch confirmation).
  7. Report  - Clean structured receipt of all actions.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def render_table(rows: list[dict], columns: list[str] | None = None, headers: list[str] | None = None) -> str:
    if not rows:
        return "*(no records)*\n"
    if columns is None:
        columns = list(rows[0].keys())
    if headers is None:
        headers = [col.replace("_", " ").title() for col in columns]

    col_widths = [len(h) for h in headers]
    for r in rows:
        for idx, col in enumerate(columns):
            val_str = str(r.get(col, "")).replace("\n", " ").strip()
            if len(val_str) > col_widths[idx]:
                col_widths[idx] = len(val_str)

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    row_lines = []
    for r in rows:
        row_str = "| " + " | ".join(str(r.get(col, "")).replace("\n", " ").strip().ljust(col_widths[i]) for i, col in enumerate(columns)) + " |"
        row_lines.append(row_str)
    return "\n".join([header_line, sep_line] + row_lines) + "\n"

SECRET_FILE_PATTERNS = [
    r"^\.env(?!\.example$)",
    r"\.pem$",
    r"\.key$",
    r"^id_rsa",
    r"\.pfx$",
    r"\.p12$",
    r"credentials\.json$",
]

SECRET_CONTENT_PATTERNS = [
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI / API Secret Key"),
    (r"AIza[0-9A-Za-z-_]{35}", "Google API Key"),
    (r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----", "Private Key Header"),
]


def run_git(args: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, check=check, text=True, capture_output=capture)


def stage1_look() -> dict:
    # 1. Branch name
    res = run_git(["branch", "--show-current"])
    branch = res.stdout.strip()
    if not branch:
        sys.exit("❌ Error: Detached HEAD state. Please switch to a branch before syncing.")

    # 2. Check for active rebase/merge/cherry-pick
    git_dir = Path(run_git(["rev-parse", "--git-dir"]).stdout.strip())
    if (git_dir / "MERGE_HEAD").is_file():
        sys.exit("❌ Error: A merge is currently in progress. Resolve or abort before running git-sync.")
    if (git_dir / "rebase-merge").is_dir() or (git_dir / "rebase-apply").is_dir():
        sys.exit("❌ Error: A rebase is currently in progress. Complete or abort before running git-sync.")
    if (git_dir / "CHERRY_PICK_HEAD").is_file():
        sys.exit("❌ Error: A cherry-pick is currently in progress.")

    # 3. Check upstream tracking
    has_upstream = False
    ahead, behind = 0, 0
    try:
        up_res = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"])
        upstream = up_res.stdout.strip()
        has_upstream = bool(upstream)
        run_git(["fetch"], check=False)
        count_res = run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        parts = count_res.stdout.strip().split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
    except subprocess.CalledProcessError:
        upstream = None

    # 4. Check status
    status_res = run_git(["status", "--porcelain"])
    changed_files = [line[3:].strip() for line in status_res.stdout.splitlines() if line.strip()]

    return {
        "branch": branch,
        "upstream": upstream,
        "has_upstream": has_upstream,
        "ahead": ahead,
        "behind": behind,
        "changed_files": changed_files,
    }


def stage2_guard(changed_files: list[str]) -> list[str]:
    safe_files = []
    blocked_files = []

    for f_str in changed_files:
        p = Path(f_str)
        fname = p.name

        # 1. Filename secret checks
        is_secret = any(re.search(pat, fname, re.IGNORECASE) for pat in SECRET_FILE_PATTERNS)
        if is_secret:
            blocked_files.append((f_str, "Secret file pattern blocked"))
            continue

        # 2. Oversized blob check (>50 MB)
        if p.is_file() and p.stat().st_size > 50 * 1024 * 1024:
            blocked_files.append((f_str, f"Oversized file ({p.stat().st_size // (1024*1024)} MB > 50 MB ceiling)"))
            continue

        # 3. Diff content secret scan
        if p.is_file():
            try:
                diff_res = run_git(["diff", "HEAD", "--", f_str], check=False)
                diff_text = diff_res.stdout
                leak_found = False
                for pat, label in SECRET_CONTENT_PATTERNS:
                    if re.search(pat, diff_text):
                        blocked_files.append((f_str, f"Diff contains leaked {label}"))
                        leak_found = True
                        break
                if leak_found:
                    continue
            except Exception:
                pass

        safe_files.append(f_str)

    if blocked_files:
        print("\n🛡️  [Security Guard] Blocked files from staging:")
        for bf, reason in blocked_files:
            print(f"   ❌ {bf} — {reason}")

    return safe_files, blocked_files


def stage3_commit(safe_files: list[str], message: str = None) -> list[str]:
    committed_shas = []
    if not safe_files:
        return committed_shas

    # Stage explicitly by path (NEVER git add -A or git add .)
    for f in safe_files:
        if Path(f).exists():
            run_git(["add", "--", f])
        else:
            run_git(["rm", "--cached", "--", f], check=False)

    commit_msg = message
    if not commit_msg:
        # Default commit message following conventional commits
        if len(safe_files) == 1:
            commit_msg = f"fix: update {Path(safe_files[0]).name}"
        else:
            commit_msg = f"feat: sync {len(safe_files)} changed files"

    res = run_git(["commit", "-m", commit_msg])
    # Extract SHA
    sha_res = run_git(["rev-parse", "--short", "HEAD"])
    committed_shas.append((sha_res.stdout.strip(), commit_msg))
    return committed_shas


def stage4_gate():
    """Run fast repository quality checks before pulling/pushing."""
    root = Path.cwd()
    checks_run = []

    # 1. Node / TypeScript checks
    if (root / "package.json").is_file():
        # Check typecheck
        pkg_content = (root / "package.json").read_text(encoding="utf-8", errors="replace")
        if '"typecheck"' in pkg_content:
            checks_run.append("npm run typecheck")
            subprocess.run(["npm", "run", "typecheck"], check=True)
        elif '"test"' in pkg_content and '"test": "echo' not in pkg_content:
            checks_run.append("npm test")
            subprocess.run(["npm", "test"], check=True)

    # 2. Python checks
    elif (root / "pytest.ini").is_file() or (root / "pyproject.toml").is_file():
        if shutil.which("pytest") and (root / "tests").is_dir():
            checks_run.append("pytest")
            subprocess.run(["pytest", "-q"], check=True)

    return checks_run


def stage5_pull(upstream: str):
    if not upstream:
        return "No upstream tracking branch"

    # Merge pull (--no-rebase per super-board specification)
    res = run_git(["pull", "--no-rebase"], check=False)
    if res.returncode != 0:
        sys.exit(f"❌ Error: Merge conflict detected during pull:\n{res.stdout}\n{res.stderr}\nPlease resolve conflicts manually.")
    return "Clean merge (up to date)"


def stage6_push(branch: str, has_upstream: bool, auto_yes: bool = False):
    is_protected = branch in ("main", "master", "production")
    if is_protected and not auto_yes:
        confirm = input(f"⚠️  Branch '{branch}' is a protected default branch. Confirm push to remote? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            sys.exit("Push cancelled by user.")

    if not has_upstream:
        run_git(["push", "-u", "origin", branch])
    else:
        run_git(["push"])


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="git-sync",
        description="Disciplined 6-Stage Git Branch Synchronization Engine (Look -> Guard -> Commit -> Gate -> Pull -> Push -> Report)"
    )
    parser.add_argument("-m", "--message", help="Commit message (default: auto conventional summary)")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm push to protected default branches (main/master)")
    parser.add_argument("--no-pull", action="store_true", help="Skip pulling from remote before pushing")
    parser.add_argument("--no-gate", action="store_true", help="Skip pre-push automated test/lint gates")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and display actions without committing or pushing")

    parser.add_argument("--table", "-t", action="store_true", help="Emit receipt as Markdown table")
    parser.add_argument("--json", action="store_true", help="Emit receipt as JSON")

    args = parser.parse_args(argv)

    # Stage 1: Look
    look_info = stage1_look()
    branch = look_info["branch"]
    changed = look_info["changed_files"]

    if not changed and look_info["ahead"] == 0 and look_info["behind"] == 0:
        if args.json:
            print(json.dumps({"status": "clean", "branch": branch, "message": "Branch is clean and in sync with remote."}, indent=2))
        else:
            print(f"✨ Branch '{branch}' is clean and in sync with remote.")
        return

    # Stage 2: Guard
    safe_files, blocked_files = stage2_guard(changed)

    if args.dry_run:
        if args.json:
            print(json.dumps({
                "status": "dry_run",
                "branch": branch,
                "safe_files": safe_files,
                "blocked_files": blocked_files,
                "ahead": look_info["ahead"],
                "behind": look_info["behind"]
            }, indent=2))
        else:
            print(f"\n🔍 [git-sync DRY-RUN] Status for branch '{branch}':")
            print(f"   Safe to stage ({len(safe_files)}): {', '.join(safe_files) if safe_files else 'none'}")
            print(f"   Blocked ({len(blocked_files)}): {', '.join([f[0] for f in blocked_files]) if blocked_files else 'none'}")
            print(f"   Ahead: {look_info['ahead']} | Behind: {look_info['behind']}")
        return

    # Stage 3: Commit
    committed = []
    if safe_files:
        committed = stage3_commit(safe_files, message=args.message)

    # Stage 4: Gate
    if not args.no_gate:
        try:
            gates = stage4_gate()
        except subprocess.CalledProcessError as e:
            sys.exit(f"❌ Error: Pre-push quality gate failed with exit code {e.returncode}. Commit created, but push halted.")

    # Stage 5: Pull
    pull_status = "Skipped"
    if not args.no_pull and look_info["has_upstream"]:
        pull_status = stage5_pull(look_info["upstream"])

    # Stage 6: Push
    stage6_push(branch, look_info["has_upstream"], auto_yes=args.yes)

    # Stage 7: Report
    if args.json:
        receipt = {
            "status": "ok",
            "branch": branch,
            "commits": [{"sha": sha, "message": msg} for sha, msg in committed],
            "pull": pull_status,
            "push": f"Pushed to {branch}",
            "blocked": [{"file": bf, "reason": r} for bf, r in blocked_files]
        }
        print(json.dumps(receipt, indent=2))
        return

    if args.table:
        rows = [
            {"step": "Branch", "status": branch, "details": look_info.get("upstream") or "local only"},
            {"step": "Commit", "status": f"{len(committed)} commit(s)" if committed else "Clean", "details": ", ".join(f"{s} {m}" for s, m in committed) if committed else "Working tree clean"},
            {"step": "Pull", "status": pull_status, "details": "Merged remote changes" if "Auto" in pull_status else pull_status},
            {"step": "Push", "status": "Success", "details": f"Pushed upstream to {branch}"},
            {"step": "Left Out", "status": f"{len(blocked_files)} blocked" if blocked_files else "None", "details": ", ".join(bf for bf, _ in blocked_files) if blocked_files else "Clean"},
        ]
        print(f"### git-sync Receipt: `{branch}`\n")
        print(render_table(rows, ["step", "status", "details"]))
        return

    print("\n📋 \033[1m[git-sync Receipt]\033[0m")
    print("─" * 60)
    if committed:
        for sha, msg in committed:
            print(f"   Committed  : {sha} {msg}")
    else:
        print("   Committed  : None (clean working tree)")

    print(f"   Pull       : {pull_status}")
    print(f"   Push       : Successfully pushed to {branch}")

    if blocked_files:
        print("   Left out   :")
        for bf, reason in blocked_files:
            print(f"     • {bf} ({reason})")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    main()
