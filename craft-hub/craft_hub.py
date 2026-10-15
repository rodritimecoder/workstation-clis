#!/usr/bin/env python3
"""
craft_hub.py — Uber Protocol & DoorDash API for Code Craft, Audits, and Rigorous Reviews
Unified late-binding dispatch gateway for 9 elite engineering kitchens:
Ponytail, pstack, Poteto Mode, Thermo-Nuclear, Unslop, Verification, No-Comments, and TypeScript.
Features full Response Projection (--project) and Disk Buffering (--out) to eliminate context bloat.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
if SCRIPT_PATH.parent.name == "scripts":
    CRAFT_HUB_DIR = SCRIPT_PATH.parent.parent
else:
    CRAFT_HUB_DIR = SCRIPT_PATH.parent

KITCHENS_DIR = CRAFT_HUB_DIR / "kitchens"
SKILLS_DIR = Path("/run/media/rodri/AI/skills")

KITCHENS = {
    "ponytail": {
        "name": "Ponytail Suite",
        "emoji": "🍔",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/rubric.md",
        "tags": ["minimal diff", "yagni", "lazy dev", "simplest solution", "delete bloat", "least code"],
        "description": "The best code is the code never written. Solves the whole problem with the least new code. Deletion beats addition.",
        "related": ["ponytail-review", "ponytail-audit", "ponytail-debt", "ponytail-gain", "ponytail-help"]
    },
    "ponytail-audit": {
        "name": "Ponytail Whole-Repo Audit",
        "emoji": "🔍",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/audit.md",
        "tags": ["audit", "whole repo", "dead code", "bugs", "load breaks"],
        "description": "Quality audit of a whole repo: bugs, security holes, load breaks, risky untested code, and what to delete.",
        "related": ["ponytail", "ponytail-review"]
    },
    "ponytail-review": {
        "name": "Ponytail Code Review",
        "emoji": "🧐",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/review.md",
        "tags": ["code review", "review diff", "safety", "tests", "minimal diff"],
        "description": "Quality review of a change: correctness, safety, load resilience, test coverage, and lean diff.",
        "related": ["ponytail", "ponytail-audit"]
    },
    "ponytail-debt": {
        "name": "Ponytail Debt Ledger",
        "emoji": "📝",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/debt.md",
        "tags": ["debt", "shortcuts", "todo", "fixme", "deferred"],
        "description": "Scans for shortcut/ponytail comments and deferred items across the repo as an actionable ledger.",
        "related": ["ponytail"]
    },
    "ponytail-gain": {
        "name": "Ponytail Benchmark & Gain",
        "emoji": "📊",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/gain.md",
        "tags": ["benchmark", "cost", "speed", "savings"],
        "description": "Measured savings and benchmarks for ponytail mode.",
        "related": ["ponytail"]
    },
    "ponytail-help": {
        "name": "Ponytail Help & Quick Reference",
        "emoji": "❓",
        "chef": "The Lazy Senior Developer",
        "rubric_path": "ponytail/help.md",
        "tags": ["help", "reference", "cheatsheet"],
        "description": "Quick reference card for ponytail levels, skills, and commands.",
        "related": ["ponytail"]
    },
    "pstack": {
        "name": "pstack Playbooks",
        "emoji": "🍣",
        "chef": "Lauren Tan (Cursor / React Core)",
        "rubric_path": "pstack/rubric.md",
        "tags": ["playbooks", "investigation", "hillclimb", "runtime forensics", "shipping", "babysit", "prototype", "rigorous"],
        "description": "23 battle-tested engineering playbooks for deep agent autonomy, systematic triage, and rigorous verification.",
        "related": ["poteto", "create-verification"]
    },
    "poteto": {
        "name": "Poteto Mode",
        "emoji": "🥗",
        "chef": "Foundational Architecture Discipline",
        "rubric_path": "poteto/rubric.md",
        "tags": ["domain modeling", "state matrix", "foundational thinking", "laziness protocol", "state machine", "type discipline", "verified execution"],
        "description": "Encode the domain into state machines, pre-implementation transition matrices, and types instead of scattered conditionals.",
        "related": ["pstack", "typescript"]
    },
    "thermonuclear": {
        "name": "Thermo-Nuclear Review",
        "emoji": "🍕",
        "chef": "Harsh Architectural Auditor",
        "rubric_path": "thermonuclear/rubric.md",
        "tags": ["harsh review", "maintainability", "1000 line ceiling", "anti-spaghetti", "structural judo", "architecture audit"],
        "description": "Unusually strict maintainability review. Enforces 1,000-line ceiling, forbids spaghetti conditionals, and seeks structural deletion judo.",
        "related": []
    },
    "unslop": {
        "name": "Unslop Prose",
        "emoji": "🍜",
        "chef": "Human Voice Enforcer",
        "rubric_path": "unslop/rubric.md",
        "tags": ["ai tells", "unslop", "human writing", "no fluff", "active voice", "cut jargon", "anti-bot"],
        "description": "31-rule precision scanner that strips AI tell patterns: superficial -ing, fake ranges, sycophancy, fancy synonyms, and robotic hedging.",
        "related": []
    },
    "create-verification": {
        "name": "Create Verification Skill",
        "emoji": "🔬",
        "chef": "The Grounded Verifier",
        "rubric_path": "pstack/skills/create-verification-skill/rubric.md",
        "tags": ["verification", "test harness", "requirement traceability", "drive", "doctor", "launch", "evidence", "feature map", "prove it works"],
        "description": "Generate a project-local verification skill with Launch, Doctor, Drive, Evidence, Cleanup, and [REQ-XX] Feature Map.",
        "related": ["maintain-verification", "poteto"]
    },
    "maintain-verification": {
        "name": "Maintain Verification Skill",
        "emoji": "🧪",
        "chef": "The Drift Hunter",
        "rubric_path": "pstack/skills/maintain-verification-skill/rubric.md",
        "tags": ["verify audit", "drift check", "live pass", "feature map upkeep", "doctor check", "evidence"],
        "description": "Periodic upkeep pass that checks source drift, drives every mapped feature live, verifies health with Doctor, and flags product regressions.",
        "related": ["create-verification", "poteto"]
    },
    "no-comments": {
        "name": "No Comments (Comment Sicko)",
        "emoji": "✂️",
        "chef": "Comment Sicko",
        "rubric_path": "pstack/skills/no-comments/rubric.md",
        "tags": ["clean code", "no comments", "comment sicko", "strip ai fluff", "encode constraints", "types over comments"],
        "description": "Eliminate redundant code comments, strip AI commentary, and encode real constraints into types, runtime assertions, or linter rules.",
        "related": ["ponytail", "typescript"]
    },
    "typescript": {
        "name": "TypeScript Best Practices",
        "emoji": "🛡️",
        "chef": "Type Discipline Enforcer",
        "rubric_path": "pstack/skills/typescript-best-practices/rubric.md",
        "tags": ["typescript", "ts discipline", "discriminated unions", "branded types", "no as casts", "satisfies", "schemas"],
        "description": "Discriminated unions, branded types, constructive modeling, schemas before guards, zero 'as' casts, and 'satisfies' over 'as'.",
        "related": ["poteto", "no-comments"]
    }
}

UNSLOP_PATTERNS = [
    (r"\b(crucial|delve|enduring|enhance|fostering|garner|interplay|intricate|pivotal|showcase|tapestry|testament|underscore|vibrant)\b", "AI Vocabulary Tell"),
    (r"\b(not just [^,\n]+, but)\b", "Not just X, but Y construction"),
    (r"\b(serves as|stands as|boasts|features)\b", "Fancy way to say 'is/has'"),
    (r"\b(in order to)\b", "Wordy filler (use 'to')"),
    (r"\b(due to the fact that)\b", "Wordy filler (use 'because')"),
    (r"\b(it is important to note that)\b", "Chatbot preamble filler"),
    (r"\b(I hope this helps|Let me know if|Certainly!|Of course!)\b", "Chatbot sycophantic artifact"),
    (r"—", "Em dash tell (use period or comma)"),
]


def resolve_skill_file(rel_path: str) -> Path:
    candidates = [
        KITCHENS_DIR / rel_path,
        KITCHENS_DIR / f"{rel_path}.md",
        KITCHENS_DIR / rel_path / "rubric.md",
        SKILLS_DIR / rel_path / "SKILL.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


def cmd_menu(as_json=False):
    if as_json:
        data = [
            {"id": k_id, "name": info["name"], "chef": info["chef"], "description": info["description"], "tags": info["tags"]}
            for k_id, info in KITCHENS.items()
        ]
        print(json.dumps(data, indent=2))
        return

    print("\n🍽️  [Uber / DoorDash Code Craft Hub] Available Kitchens Menu:\n")
    print(f"{'#':<3} {'Kitchen':<22} {'Chef / Origin':<32} {'Specialty & Vibe'}")
    print("─" * 80)
    for i, (k_id, info) in enumerate(KITCHENS.items(), start=1):
        chef_str = f"{info['emoji']} {info['name']}"
        print(f"{i:<3} {chef_str:<22} {info['chef']:<32} {info['description'][:60]}...")
    print("\n💡 Commands: 'craft-hub inspect <kitchen>' | 'craft-hub order <kitchen> [target]'\n")


def cmd_search(query: str, as_json=False):
    tokens = query.lower().split()
    scored = []
    for k_id, info in KITCHENS.items():
        score = 0
        haystack = f"{k_id} {info['name']} {info['chef']} {info['description']} {' '.join(info['tags'])}".lower()
        for t in tokens:
            if t in k_id:
                score += 10
            if t in info['name'].lower():
                score += 6
            if t in haystack:
                score += 3
        if score > 0:
            scored.append((score, k_id, info))

    scored.sort(key=lambda x: x[0], reverse=True)
    if as_json:
        results = [
            {"id": k_id, "name": info["name"], "score": score, "description": info["description"], "tags": info["tags"]}
            for score, k_id, info in scored
        ]
        print(json.dumps(results, indent=2))
        return

    if not scored:
        print(f"\n🔍 No kitchens matched '{query}'. Run 'craft-hub menu' to see available options.\n")
        return

    print(f"\n🔍 [Uber Protocol Craft Search] Results for '{query}':\n")
    for score, k_id, info in scored:
        print(f"  • {info['emoji']} \033[1m{info['name']}\033[0m (`{k_id}`) — {info['chef']}")
        print(f"    {info['description']}")
        print(f"    Tags: {', '.join(info['tags'][:4])}\n")


def cmd_inspect(kitchen_id: str):
    k_id = kitchen_id.lower().replace("-", "")
    info = KITCHENS.get(kitchen_id.lower()) or KITCHENS.get(k_id)
    if not info:
        for key in KITCHENS:
            if key.startswith(k_id):
                info = KITCHENS[key]
                break

    if not info:
        print(f"❌ Unknown kitchen '{kitchen_id}'. Available: {', '.join(KITCHENS.keys())}")
        sys.exit(1)

    skill_file = resolve_skill_file(info.get("rubric_path", info.get("skill_dir", "")))
    if not skill_file.is_file():
        print(f"❌ Skill file not found: {skill_file}")
        sys.exit(1)

    content = skill_file.read_text(encoding="utf-8")
    print(f"\n📜 [Kitchen Recipe & Rubric] {info['emoji']} {info['name']} ({skill_file})\n")
    print("=" * 80)
    print(content)
    print("=" * 80)


def scan_unslop(text: str):
    findings = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, label in UNSLOP_PATTERNS:
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for m in matches:
                findings.append({
                    "line": idx,
                    "label": label,
                    "match": m.group(0),
                    "context": line.strip()[:80]
                })
    return findings


def get_git_diff():
    try:
        out = subprocess.check_output(["git", "diff", "HEAD"], stderr=subprocess.DEVNULL, text=True)
        if not out.strip():
            out = subprocess.check_output(["git", "diff"], stderr=subprocess.DEVNULL, text=True)
        return out
    except Exception:
        return ""


def get_git_touched_files():
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], stderr=subprocess.DEVNULL, text=True)
        files = [f.strip() for f in out.splitlines() if f.strip() and Path(f.strip()).is_file()]
        if not files:
            out2 = subprocess.check_output(["git", "diff", "--name-only"], stderr=subprocess.DEVNULL, text=True)
            files = [f.strip() for f in out2.splitlines() if f.strip() and Path(f.strip()).is_file()]
        return files
    except Exception:
        return []


def cmd_order(kitchen_id: str, target: str = None, out_path: str = None, project_fields: str = None, as_json: bool = False):
    k_id = kitchen_id.lower().replace("-", "")

    # Grand combo platter
    if k_id == "combo":
        results = {}
        for sub_k in ["ponytail", "pstack", "poteto", "thermonuclear", "unslop", "typescript", "no-comments"]:
            sub_res = evaluate_kitchen(sub_k, target)
            results[sub_k] = sub_res

        if as_json or project_fields or out_path:
            full_json = json.dumps(results, indent=2)
            if out_path:
                Path(out_path).write_text(full_json, encoding="utf-8")
                print(f"[Combo Audit Complete. Full trace buffered to {out_path}]")
            else:
                print(full_json)
        else:
            print("\n🍱 [Uber / DoorDash Grand Combo Platter] Audit across ALL Kitchens:\n" + "=" * 70)
            for sub_k, res in results.items():
                print(f"\n{res['emoji']} {res['name']}: {res['status']}")
                for check in res.get("checks", []):
                    print(f"   • {check}")
        return

    res = evaluate_kitchen(kitchen_id, target)
    if as_json or project_fields or out_path:
        if project_fields:
            fields = [f.strip() for f in project_fields.split(",")]
            res = {k: v for k, v in res.items() if k in fields}
        full_json = json.dumps(res, indent=2)
        if out_path:
            Path(out_path).write_text(full_json, encoding="utf-8")
            print(f"[Audit Complete for {res.get('name', kitchen_id)}. Output buffered to {out_path}]")
        else:
            print(full_json)
    else:
        print(f"\n📦 \033[1m[Order Dispatched]\033[0m {res['emoji']} \033[1m{res['name']}\033[0m")
        print(f"   👨‍🍳 Chef: {res['chef']}")
        print(f"   🎯 Lens: {res['description']}")
        print(f"   🔍 Target: {res['target_desc']}")
        print("─" * 70)
        for check in res.get("checks", []):
            print(f"   {check}")
        print(f"\n📋 [Review Rubric Available in {res['skill_file']}]")


def evaluate_kitchen(kitchen_id: str, target: str = None) -> dict:
    k_id = kitchen_id.lower().replace("-", "")
    info = KITCHENS.get(kitchen_id.lower()) or KITCHENS.get(k_id)
    if not info:
        for key in KITCHENS:
            if key.startswith(k_id):
                info = KITCHENS[key]
                k_id = key
                break

    if not info:
        return {"error": f"Unknown kitchen '{kitchen_id}'"}

    target_text = ""
    is_git_diff = False
    target_desc = ""

    if target and Path(target).is_file():
        target_desc = f"File: {target}"
        target_text = Path(target).read_text(encoding="utf-8", errors="replace")
    elif target and Path(target).is_dir():
        target_desc = f"Directory: {target}"
    else:
        diff = get_git_diff()
        if diff:
            target_desc = "Current Git Diff (staged + unstaged)"
            target_text = diff
            is_git_diff = True
        else:
            target_desc = "Workspace Codebase"

    checks = []
    status = "OK"

    if k_id == "thermonuclear":
        touched = get_git_touched_files() if is_git_diff else ([target] if target and Path(target).is_file() else [])
        if touched:
            for tf in touched:
                try:
                    lines = len(Path(tf).read_text(encoding="utf-8", errors="replace").splitlines())
                    if lines > 1000:
                        checks.append(f"❌ VIOLATION: {tf} is {lines} lines (>1,000 ceiling)")
                        status = "VIOLATION"
                    else:
                        checks.append(f"✅ OK: {tf} is {lines} lines (<1,000 lines)")
                except Exception:
                    pass
        else:
            checks.append("• Clean working tree or no diff for file size audit.")

    elif k_id in ["ponytail", "ponytailreview"]:
        if target_text and is_git_diff:
            added = sum(1 for line in target_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
            deleted = sum(1 for line in target_text.splitlines() if line.startswith("-") and not line.startswith("---"))
            checks.append(f"• Diff Volume: +{added} / -{deleted} (Net: {added - deleted:+d} lines)")
            if added > 150:
                checks.append("⚠️  Caution: Large addition (>150 lines). Can this be solved with less new code?")
                status = "WARNING"
            else:
                checks.append("✅ Diff volume is compact and minimal.")
        else:
            checks.append("• Clean working tree or no diff to calculate delta.")

    elif k_id in ["ponytaildebt", "debt"]:
        debt_items = []
        try:
            res = subprocess.run(["git", "grep", "-En", r"(//|#)\s*(shortcut|ponytail|TODO|FIXME):"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                debt_items = res.stdout.strip().splitlines()
        except Exception:
            pass
        if debt_items:
            checks.append(f"📝 Found {len(debt_items)} recorded shortcut/debt item(s):")
            for item in debt_items[:8]:
                checks.append(f"   {item.strip()}")
            if len(debt_items) > 8:
                checks.append(f"   ... and {len(debt_items) - 8} more.")
        else:
            checks.append("✅ Zero unresolved shortcut: or ponytail: comments found in repository.")

    elif k_id in ["ponytailaudit", "audit"]:
        checks.append("1. Bug & Vulnerability Scan: Search for unchecked inputs, loose type casts, and state leaks.")
        checks.append("2. Dead Code Removal: Identify orphaned files, uncalled functions, and dead dependencies.")
        checks.append("3. Real Load Resilience: Verify timeouts, failure handling, and retry bounds.")

    elif k_id == "unslop":
        findings = scan_unslop(target_text) if target_text else []
        if findings:
            checks.append(f"⚠️  Found {len(findings)} potential AI tell pattern(s):")
            for f in findings[:6]:
                checks.append(f"   [Line {f['line']}] {f['label']}: \"{f['match']}\"")
            status = "WARNING"
        else:
            checks.append("✅ Clean! Zero obvious AI tell words detected.")

    elif k_id in ["pstack", "poteto"]:
        checks.append("1. Model the Domain: States as explicit unions/state machines instead of loose flags.")
        checks.append("2. Laziness Protocol: Deletion beats addition; verify every line is strictly necessary.")
        checks.append("3. Grounded Artifacts: Never trust assumptions; verify with real command execution.")

    elif "typescript" in k_id or k_id == "ts":
        touched = get_git_touched_files() if is_git_diff else ([target] if target and Path(target).is_file() else [])
        ts_files = [f for f in touched if f.endswith((".ts", ".tsx"))]
        if ts_files:
            any_count = 0
            as_count = 0
            for tf in ts_files:
                try:
                    content = Path(tf).read_text(encoding="utf-8", errors="replace")
                    any_count += len(re.findall(r":\s*any\b", content))
                    as_count += len(re.findall(r"\bas\s+[A-Z]", content))
                except Exception:
                    pass
            checks.append(f"• Scanned {len(ts_files)} TypeScript file(s)")
            if any_count > 0:
                checks.append(f"⚠️ Found {any_count} loose 'any' annotations. (Prefer 'unknown' or domain types)")
                status = "WARNING"
            if as_count > 0:
                checks.append(f"⚠️ Found {as_count} unvalidated 'as' casts. (Prefer 'satisfies' or type guards)")
                status = "WARNING"
            if any_count == 0 and as_count == 0:
                checks.append("✅ Zero unvalidated 'any' or risky 'as' casts detected.")
        else:
            checks.append("• No modified .ts/.tsx files found to scan.")

    elif "nocomments" in k_id or "no-comments" in k_id:
        touched = get_git_touched_files() if is_git_diff else ([target] if target and Path(target).is_file() else [])
        code_files = [f for f in touched if not f.endswith((".md", ".txt", ".json", ".yaml", ".yml"))]
        if code_files:
            for cf in code_files[:5]:
                try:
                    lines = Path(cf).read_text(encoding="utf-8", errors="replace").splitlines()
                    comment_lines = sum(1 for l in lines if re.match(r"^\s*(//|#|/\*|\*)", l))
                    ratio = (comment_lines / len(lines) * 100) if lines else 0
                    if ratio > 25:
                        checks.append(f"⚠️ {cf}: {comment_lines}/{len(lines)} lines are comments ({ratio:.1f}%). Strip trivial comments.")
                        status = "WARNING"
                    else:
                        checks.append(f"✅ {cf}: comment ratio clean ({ratio:.1f}%)")
                except Exception:
                    pass
        else:
            checks.append("• No modified code files found to audit comments.")

    skill_file = resolve_skill_file(info.get("rubric_path", info.get("skill_dir", "")))
    return {
        "kitchen_id": k_id,
        "name": info["name"],
        "emoji": info["emoji"],
        "chef": info["chef"],
        "description": info["description"],
        "target_desc": target_desc,
        "status": status,
        "checks": checks,
        "skill_file": str(skill_file),
    }


def main():
    parser = argparse.ArgumentParser(
        prog="craft-hub",
        description="The Uber Protocol & DoorDash API for Code Craft, Audits, and Rigorous Reviews"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_menu = sub.add_parser("menu", help="List all kitchens and their specialties")
    p_menu.add_argument("--json", action="store_true", help="Output menu as JSON")

    sub.add_parser("list", help="Alias for menu")

    p_search = sub.add_parser("search", help="Search kitchens by intent or keyword")
    p_search.add_argument("query", help="Intent query (e.g. 'harsh audit', 'delete bloat')")
    p_search.add_argument("--json", action="store_true", help="Output results as JSON")

    p_inspect = sub.add_parser("inspect", help="Read a kitchen's full rubric and rules")
    p_inspect.add_argument("kitchen", help="Kitchen name (ponytail, pstack, poteto, thermonuclear, unslop, combo)")

    p_order = sub.add_parser("order", help="Dispatch a review order on git diff or target file")
    p_order.add_argument("kitchen", help="Kitchen name (ponytail, pstack, poteto, thermonuclear, unslop, combo)")
    p_order.add_argument("target", nargs="?", default=None, help="Optional file or directory path")
    p_order.add_argument("--out", default=None, help="Buffer raw audit output to disk file")
    p_order.add_argument("--project", default=None, help="Comma-separated fields to project (e.g. 'status,checks')")
    p_order.add_argument("--json", action="store_true", help="Output audit results as JSON")

    args = parser.parse_args()
    if args.action in ["menu", "list"]:
        cmd_menu(as_json=getattr(args, "json", False))
    elif args.action == "search":
        cmd_search(args.query, as_json=args.json)
    elif args.action == "inspect":
        cmd_inspect(args.kitchen)
    elif args.action == "order":
        cmd_order(args.kitchen, args.target, out_path=args.out, project_fields=args.project, as_json=args.json)


if __name__ == "__main__":
    main()
