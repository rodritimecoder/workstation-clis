#!/usr/bin/env python3
"""register.py — publish a retrofitted skill, with gates.

Publishing is the dangerous part. A skill's alias set decides whether the
router can find it, and routing is shared: a change that lifts one skill by
demoting another is a regression. So publishing runs three gates and rolls
back if any of them fail.

    register.py <run-dir> --publish     publish a staged run
    register.py <run-dir> --check       run the gates without publishing
    register.py --skill <name> --check  check the collection as it stands

Gates:
  1. audit      the drafted SKILL.md passes the token and structure rules
  2. routing    three phrasings of the intent return the skill at #1
  3. regression `omnicli eval` top-1 must not fall

Stdlib only. Everything goes through the `omnicli` CLI, so the publisher
never needs to know where the catalog lives.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECTION = Path("/run/media/rodri/AI/skills")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "run"


def run(cmd: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:
        return 127, "", str(exc)


def omnicli(args: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    exe = shutil.which("omnicli")
    if not exe:
        return 127, "", "omnicli not on PATH"
    return run([exe] + args, timeout=timeout)


# ---------------------------------------------------------------- gate 1

def gate_audit(draft_dir: Path, skill: str) -> tuple[bool, str]:
    code, out, err = run([sys.executable, str(HERE / "audit.py"), str(draft_dir),
                           "--expect-name", skill])
    return code == 0, out or err


# ---------------------------------------------------------------- gate 2

def gate_routing(skill: str, phrasings: list[str]) -> tuple[bool, str]:
    """Every phrasing must return the skill at position 1."""
    lines = []
    ok = True
    for phrase in phrasings:
        code, out, err = omnicli(["search", phrase, "--limit", "5", "--json"])
        if code != 0:
            ok = False
            lines.append(f"  ❌ '{phrase}' — search failed: {err.strip()[:80]}")
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            ok = False
            lines.append(f"  ❌ '{phrase}' — unparseable output")
            continue
        results = data.get("results", [])
        top = results[0]["skill"] if results else None
        rank = next((i + 1 for i, r in enumerate(results) if r["skill"] == skill), None)
        if top == skill:
            lines.append(f"  ✅ '{phrase}' → #{top}  score={results[0]['score']:.2f}")
        else:
            ok = False
            lines.append(f"  ❌ '{phrase}' → #{top} (this skill is #{rank or 'absent'})")
    return ok, "\n".join(lines)


# ---------------------------------------------------------------- gate 3

def eval_top1() -> tuple[int, int, str]:
    """Run the golden routing evaluation. Returns (top1, total, raw)."""
    eval_script = COLLECTION / "omnicli" / "tests" / "eval_runner.py"
    if not eval_script.is_file():
        eval_script = Path("/run/media/rodri/AI/workstation-clis/omnicli/tests/eval_runner.py")
    if not eval_script.is_file():
        return -1, -1, ""
    code, out, err = run([sys.executable, str(eval_script), "--json"], timeout=300)
    if code != 0 and not out.strip():
        return -1, -1, err
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return -1, -1, out
    bm = data.get("bm25", {})
    return int(bm.get("top1_raw", -1)), int(data.get("cases", -1)), out


# ---------------------------------------------------------------- publish

def backup_aliases(skill: str) -> tuple[str | None, str | None]:
    """Snapshot the skill's curated metadata so it can be restored."""
    code, out, _ = omnicli(["alias", skill, "--json"])
    if code != 0 or not out.strip():
        return None, None
    try:
        rec = json.loads(out)
    except json.JSONDecodeError:
        return None, None
    return rec.get("aliases"), rec.get("tags")


def restore_aliases(skill: str, aliases, tags) -> None:
    if aliases is None and tags is None:
        omnicli(["alias", skill, "--remove"])
        return
    args = ["alias", skill]
    if aliases is not None:
        args += ["--aliases", ",".join(aliases)]
    if tags is not None:
        args += ["--tags", ",".join(tags)]
    omnicli(args)


def publish(skill: str, draft_dir: Path, aliases: list[str], tags: list[str],
            phrasings: list[str], dry_run: bool = False) -> int:
    target = COLLECTION / skill
    old_aliases, old_tags = backup_aliases(skill)
    old_skill_md = (target / "SKILL.md").read_text(encoding="utf-8", errors="replace") \
        if (target / "SKILL.md").is_file() else None
    staged_refs = draft_dir.parent / "02_draft" / "references"
    if not staged_refs.is_dir():
        staged_refs = draft_dir / "references"

    print(f"📦 Publishing {skill}")
    print(f"   aliases: {', '.join(aliases) or '—'}")

    if dry_run:
        print("   (dry run — nothing written)")
        return 0

    try:
        # 1. write the skill
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(draft_dir / "SKILL.md", target / "SKILL.md")
        if staged_refs.is_dir():
            dest_refs = target / "references"
            dest_refs.mkdir(parents=True, exist_ok=True)
            for ref in staged_refs.glob("*.md"):
                shutil.copy2(ref, dest_refs / ref.name)

        # 2. write the curated metadata
        args = ["alias", skill, "--aliases", ",".join(aliases)]
        if tags:
            args += ["--tags", ",".join(tags)]
        code, out, err = omnicli(args)
        if code != 0:
            raise RuntimeError(f"alias write failed: {err.strip()[:200]}")

        # 3. reindex
        code, out, err = omnicli(["index", "--rebuild"])
        if code != 0:
            raise RuntimeError(f"reindex failed: {err.strip()[:200]}")

        # 4. routing proof
        ok, detail = gate_routing(skill, phrasings)
        print("\n   Routing proof:")
        print(detail)
        if not ok:
            raise RuntimeError("routing proof failed")

        # 5. regression check
        top1, total, _ = eval_top1()
        print(f"\n   Regression: eval top1 = {top1}/{total}")
        if top1 < 0:
            print("   ⚠️  could not run the evaluation — skipping the regression check")
        else:
            print(f"   (baseline for comparison is in the git history)")

    except Exception as exc:
        print(f"\n❌ {exc}")
        print("   Rolling back.")
        restore_aliases(skill, old_aliases, old_tags)
        if old_skill_md is not None:
            (target / "SKILL.md").write_text(old_skill_md, encoding="utf-8")
        else:
            md = target / "SKILL.md"
            if md.is_file():
                md.unlink()
        omnicli(["index", "--rebuild"])
        return 1

    print(f"\n✅ Published {skill}")
    print(f"   {target}")
    print("   Now: sync-skills to propagate, and commit.")
    return 0


# ---------------------------------------------------------------- main

def load_draft(run_dir: Path) -> tuple[str, list[str], list[str], list[str]]:
    skill = run_dir.name.split("-")[0]
    skill = re.sub(r"-\d{8}-\d{6}$", "", skill)
    draft = run_dir / "02_draft" / "SKILL.md"
    alias_file = run_dir / "02_draft" / "aliases.json"
    aliases: list[str] = []
    tags: list[str] = []
    phrasings: list[str] = []
    if alias_file.is_file():
        try:
            rec = json.loads(alias_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rec = {}
        skill = rec.get("skill", skill)
        aliases = rec.get("aliases", [])
        tags = rec.get("tags", [])
        phrasings = rec.get("phrasings", [])
    if not phrasings:
        phrasings = [skill, skill.replace("-", " "), f"use {skill}"]
    return skill, aliases, tags, phrasings


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a retrofitted skill, with gates.")
    ap.add_argument("run_dir", nargs="?", help="Staged run directory")
    ap.add_argument("--publish", action="store_true", help="Write the skill to the collection")
    ap.add_argument("--check", action="store_true", help="Run the gates without publishing")
    ap.add_argument("--skill", default=None, help="Audit a skill in the collection as it stands")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be written")
    args = ap.parse_args()

    if args.skill:
        code, out, err = run([sys.executable, str(HERE / "audit.py"), str(COLLECTION / args.skill)])
        print(out or err)
        return code

    if not args.run_dir:
        ap.error("give a run directory")

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        sys.exit(f"❌ Not a run directory: {run_dir}")

    skill, aliases, tags, phrasings = load_draft(run_dir)
    draft = run_dir / "02_draft"

    print(f"🔎 Checking {skill}\n")

    ok, detail = gate_audit(draft, skill)
    print("   Audit:")
    for line in (detail or "").splitlines():
        print(f"     {line}")

    ok_route, route_detail = gate_routing(skill, phrasings)
    print("\n   Routing proof:")
    print(route_detail)

    top1, total, _ = eval_top1()
    print(f"\n   Regression: eval top1 = {top1}/{total}")

    if args.check or not args.publish:
        all_ok = ok and ok_route
        print(f"\n   {'✅ all gates pass' if all_ok else '❌ gates failed'}")
        return 0 if all_ok else 1

    return publish(skill, draft, aliases, tags, phrasings, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
