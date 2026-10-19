#!/usr/bin/env python3
"""audit.py — the deterministic gate for a generated skill.

Checks a SKILL.md against the rules that make a skill routable and cheap to
read. Every rule is derived from this collection's own best example
(``tailscale-ops``) or from a measured failure, not invented.

    audit.py <skill-dir>          audit one skill
    audit.py --all                audit every skill in the collection
    audit.py --all --json         machine-readable
    audit.py <skill-dir> --strict  warnings become failures

Exit code is 0 when the skill passes, 1 when it does not. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------- budgets

MAX_DESC_WORDS = 30
MAX_DESC_WORDS_DISAMBIGUATING = 40
MAX_BODY_WORDS = 300
MAX_PROSE_LEAF_WORDS = 40

# Section titles that should not be in a skill body. The body is read by an
# agent that already knows what it wants to do; these are the sections an
# agent skips, and they are the sections that cost the most.
BANNED_TITLES = [
    "overview", "introduction", "intro", "background", "about",
    "installation", "install", "setup", "requirements", "prerequisites",
    "when to use", "architecture", "design", "troubleshooting",
    "how it works", "internals", "notes",
]

# A skill body must not hardcode a harness path. The same skill is mirrored
# into three harness directories, so an absolute path is wrong documentation
# that happens to resolve.
HARNESS_PATH_RE = re.compile(
    r"(?:~|\$HOME|\$\{HOME\})?/\.(?:gemini/config/skills|config/opencode/skills|pi/agent/skills)"
    r"[^\s`'\"]*"
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE_RE = re.compile(r"^```([^\n]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------- helpers

def mask_fences(text: str) -> str:
    """Blank out fenced code blocks, preserving every offset and newline.

    A shell comment inside a fence looks exactly like a markdown heading
    (``# Open a URL``), so headings have to be read from a copy with the
    fences removed. Blanking rather than deleting keeps line numbers and
    character offsets valid against the original.
    """
    out = list(text)
    for m in FENCE_RE.finditer(text):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def strip_frontmatter(text: str) -> tuple[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def parse_frontmatter(fm: str) -> dict[str, str]:
    """Minimal frontmatter reader: scalars and folded blocks, no YAML dep."""
    out: dict[str, str] = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", "|", ">-", "|-"):
            block = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                block.append(lines[i].strip())
                i += 1
            out[key] = " ".join(x for x in block if x).strip().strip("\"'")
            continue
        out[key] = val.strip().strip("\"'")
        i += 1
    return out


def sections(body: str) -> list[dict]:
    """Split a body into heading sections, marking which have children.

    A heading with a deeper heading inside is a *group* (a table of contents
    for its children). A heading with no deeper heading inside is a *leaf*,
    and a leaf is what an agent actually reads.

    Headings are located in a fence-masked copy of the body, but section
    content is read from the original, so the commands inside a fence are
    still seen.
    """
    masked = mask_fences(body)
    marks = []
    for m in HEADING_RE.finditer(masked):
        marks.append({
            "start": m.start(),
            "content_start": m.end(),
            "level": len(m.group(1)),
            "title": m.group(2).strip(),
            "line": masked[: m.start()].count("\n") + 1,
        })
    for i, sec in enumerate(marks):
        end = len(body)
        has_child = False
        for j in range(i + 1, len(marks)):
            if marks[j]["level"] <= sec["level"]:
                end = marks[j]["start"]
                break
            has_child = True
        content = body[sec["content_start"]: end]
        sec["content"] = content
        sec["words"] = len(content.split())
        sec["is_group"] = has_child
        sec["fences"] = FENCE_RE.findall(content)
        # A leaf is actionable if it carries a command, or if it points at a
        # reference file — "read this for the detail" is an action too.
        sec["has_command"] = bool(sec["fences"])
        sec["has_reference"] = bool(re.search(r"`[^`]*\.md`|\]\([^)]*\.md\)", content))
        sec["has_action"] = sec["has_command"] or sec["has_reference"]
    return marks


def word_count(text: str) -> int:
    return len(text.split())


def approx_tokens(text: str) -> int:
    """Rough token estimate. Characters/4 is the standard approximation."""
    return max(1, len(text) // 4)


def resolve_command(token: str, skill_dir: Path) -> bool:
    """Is the first word of a command something that exists?"""
    token = token.strip().strip("\"'")
    if not token:
        return True
    if token.startswith((".", "/", "~", "$")):
        p = Path(token.replace("~", str(Path.home()), 1))
        if p.is_file() or p.is_dir():
            return True
        try:
            if (skill_dir / token.lstrip("./")).exists():
                return True
        except OSError:
            pass
        # A path into a harness mirror is legitimate only if it exists.
        return p.exists()
    return shutil.which(token) is not None


# ---------------------------------------------------------------- the audit

def audit_skill(skill_dir: Path, expect_name: str | None = None) -> dict:
    md = skill_dir / "SKILL.md"
    target_name = expect_name or skill_dir.name
    result: dict = {
        "skill": target_name,
        "path": str(skill_dir),
        "errors": [],
        "warnings": [],
        "info": {},
        "exists": md.is_file(),
    }
    if not md.is_file():
        result["errors"].append({"rule": "frontmatter", "detail": "no SKILL.md"})
        return result

    text = md.read_text(encoding="utf-8", errors="replace")
    fm_raw, body = strip_frontmatter(text)
    fm = parse_frontmatter(fm_raw)

    # --- rule 1: frontmatter -------------------------------------------
    if not fm_raw.strip():
        result["errors"].append({"rule": "frontmatter", "detail": "no YAML frontmatter"})
    if "name" not in fm:
        result["errors"].append({"rule": "frontmatter", "detail": "no 'name' field"})
    elif fm["name"] != target_name:
        result["errors"].append({
            "rule": "frontmatter",
            "detail": f"name '{fm['name']}' != expected '{target_name}'",
        })
    if "description" not in fm or not fm["description"].strip():
        result["errors"].append({"rule": "frontmatter", "detail": "no 'description' field"})

    # --- rule 2: description budget ------------------------------------
    desc = fm.get("description", "")
    desc_words = word_count(desc)
    budget = MAX_DESC_WORDS
    if desc_words > budget:
        result["errors"].append({
            "rule": "description-budget",
            "detail": f"{desc_words} words, budget {budget}",
        })

    # --- rule 8: body budget -------------------------------------------
    body_words = word_count(body)
    if body_words > MAX_BODY_WORDS:
        result["errors"].append({
            "rule": "body-budget",
            "detail": f"{body_words} words, budget {MAX_BODY_WORDS}",
        })

    # --- single H1 -----------------------------------------------------
    masked = mask_fences(body)
    h1s = [m for m in HEADING_RE.finditer(masked) if len(m.group(1)) == 1]
    if len(h1s) != 1:
        result["errors"].append({
            "rule": "single-h1",
            "detail": f"{len(h1s)} H1 headings, expected exactly 1",
        })

    secs = sections(body)
    leaves = [s for s in secs if not s["is_group"]]

    # --- rule 5: banned titles -----------------------------------------
    for s in secs:
        norm = re.sub(r"[^a-z ]", "", s["title"].lower()).strip()
        for banned in BANNED_TITLES:
            if norm == banned or norm.startswith(banned + " ") or norm.startswith(banned + ":"):
                result["errors"].append({
                    "rule": "banned-section",
                    "detail": f"'{s['title']}' (line {s['line']}) should move to references/",
                })
                break

    # --- rule 3: every leaf is an action --------------------------------
    prose_leaves = [s for s in leaves if not s["has_action"]]
    for s in prose_leaves:
        result["errors"].append({
            "rule": "leaf-not-action",
            "detail": f"'{s['title']}' (line {s['line']}) has no command",
        })

    # --- rule 4: prose leaves are small ---------------------------------
    big_prose = [s for s in prose_leaves if s["words"] > MAX_PROSE_LEAF_WORDS]
    for s in big_prose:
        result["errors"].append({
            "rule": "prose-leaf",
            "detail": f"'{s['title']}' (line {s['line']}) is {s['words']} words of prose",
        })

    # --- rule 6: hardcoded harness paths --------------------------------
    for m in HARNESS_PATH_RE.finditer(body):
        result["errors"].append({
            "rule": "harness-path",
            "detail": f"hardcoded harness path: {m.group(0)[:70]}",
        })

    # --- rule 7: commands resolve ---------------------------------------
    unresolved = []
    for s in secs:
        for lang, content in s["fences"]:
            if lang and lang.strip() not in ("bash", "sh", "shell", "console", ""):
                continue
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:            # a pipeline: check the first command
                    line = line.split("|")[0].strip()
                if line.startswith("sudo ") or line.startswith("env "):
                    line = line.split(None, 1)[1] if " " in line else ""
                if not line:
                    continue
                token = line.split()[0].strip("\"'")
                if not resolve_command(token, skill_dir):
                    unresolved.append(f"{token} (line {s['line']})")
                break   # one command per fence is enough
    for u in unresolved:
        result["errors"].append({"rule": "unresolved-command", "detail": u})

    result["info"] = {
        "description_words": desc_words,
        "description_tokens": approx_tokens(desc),
        "body_words": body_words,
        "body_tokens": approx_tokens(body),
        "total_tokens": approx_tokens(fm_raw) + approx_tokens(body),
        "sections": len(secs),
        "leaves": len(leaves),
        "action_leaves": len([s for s in leaves if s["has_action"]]),
        "prose_leaves": len(prose_leaves),
        "prose_words": sum(s["words"] for s in prose_leaves),
        "reclaimable_words": sum(s["words"] for s in big_prose),
        "frontmatter": fm,
    }
    result["ok"] = not result["errors"]
    return result


# ---------------------------------------------------------------- reporting

def report(result: dict) -> None:
    info = result["info"]
    name = result["skill"]
    if not result["exists"]:
        print(f"❌ {name}: no SKILL.md")
        return
    status = "✅ PASS" if result["ok"] else "❌ FAIL"
    print(f"\n{status}  {name}")
    print(f"   description {info['description_words']}w (~{info['description_tokens']} tok)"
          f"   body {info['body_words']}w (~{info['body_tokens']} tok)")
    print(f"   leaves {info['action_leaves']}/{info['leaves']} actionable"
          f"   prose {info['prose_words']}w"
          f"   reclaimable {info['reclaimable_words']}w")
    by_rule: dict[str, list[str]] = {}
    for e in result["errors"]:
        by_rule.setdefault(e["rule"], []).append(e["detail"])
    for rule, details in by_rule.items():
        print(f"   ❌ {rule}")
        for d in details[:6]:
            print(f"        {d}")
        if len(details) > 6:
            print(f"        ... and {len(details) - 6} more")
    for w in result["warnings"]:
        print(f"   ⚠️  {w['rule']}: {w['detail']}")


def audit_all(root: Path) -> list[dict]:
    results = []
    for item in sorted(root.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if item.name in ("glitch-cat", "archived", "docs", "launchers", "modules"):
            continue
        if not (item / "SKILL.md").is_file():
            continue
        results.append(audit_skill(item))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a skill against the routing and token rules.")
    ap.add_argument("skill", nargs="?", help="Skill directory")
    ap.add_argument("--all", action="store_true", help="Audit every skill in the collection")
    ap.add_argument("--root", default=None, help="Collection root (default: the skills dir)")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    ap.add_argument("--strict", action="store_true", help="Warnings become failures")
    ap.add_argument("--summary", action="store_true", help="Only print the summary table")
    ap.add_argument("--expect-name", default=None,
                    help="Expected frontmatter name (for auditing a draft folder)")
    args = ap.parse_args()

    if args.all:
        root = Path(args.root) if args.root else Path("/run/media/rodri/AI/skills")
        results = audit_all(root)
    elif args.skill:
        results = [audit_skill(Path(args.skill), expect_name=args.expect_name)]
    else:
        ap.error("give a skill directory or --all")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if all(r["ok"] for r in results) else 1

    if not args.summary:
        for r in results:
            report(r)

    total_desc = sum(r["info"].get("description_words", 0) for r in results)
    total_body = sum(r["info"].get("body_words", 0) for r in results)
    total_reclaim = sum(r["info"].get("reclaimable_words", 0) for r in results)
    total_prose = sum(r["info"].get("prose_words", 0) for r in results)
    failing = [r for r in results if not r["ok"]]
    print("\n" + "=" * 72)
    print(f"  {len(results)} skills audited · {len(failing)} failing")
    print(f"  descriptions {total_desc}w (~{total_desc * 13 // 10} tok)"
          f"   bodies {total_body}w (~{total_body * 13 // 10} tok)")
    print(f"  prose {total_prose}w of which {total_reclaim}w over budget → move to references/")
    print("=" * 72 + "\n")
    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
