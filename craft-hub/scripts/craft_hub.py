#!/usr/bin/env python3
"""
craft_hub.py — The DoorDash API for Code Craft, Audits, and Rigorous Reviews
Unified late-binding dispatch hub for 5 elite engineering kitchens:
Ponytail, pstack, Poteto Mode, Thermo-Nuclear, and Unslop.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path("/run/media/rodri/AI/skills")

KITCHENS = {
    "ponytail": {
        "name": "Ponytail Suite",
        "emoji": "🍔",
        "chef": "The Lazy Senior Developer",
        "skill_dir": "ponytail",
        "tags": ["minimal diff", "yagni", "lazy dev", "simplest solution", "delete bloat", "least code"],
        "description": "The best code is the code never written. Solves the whole problem with the least new code. Deletion beats addition.",
        "related": ["ponytail-review", "ponytail-audit", "ponytail-debt", "ponytail-gain", "ponytail-help"]
    },
    "pstack": {
        "name": "pstack Playbooks",
        "emoji": "🍣",
        "chef": "Lauren Tan (Cursor / React Core)",
        "skill_dir": "pstack",
        "tags": ["playbooks", "investigation", "hillclimb", "runtime forensics", "shipping", "babysit", "prototype", "rigorous"],
        "description": "23 battle-tested engineering playbooks for deep agent autonomy, systematic triage, and rigorous verification.",
        "related": ["architect", "swarm", "arena", "interrogate"]
    },
    "poteto": {
        "name": "Poteto Mode",
        "emoji": "🥗",
        "chef": "Foundational Architecture Discipline",
        "skill_dir": "poteto-mode",
        "tags": ["domain modeling", "state matrix", "foundational thinking", "laziness protocol", "state machine", "type discipline", "verified execution"],
        "description": "Encode the domain into state machines, pre-implementation transition matrices, and types instead of scattered conditionals. Never block on the human; verify against real artifacts.",
        "related": ["pstack"]
    },
    "thermonuclear": {
        "name": "Thermo-Nuclear Review",
        "emoji": "🍕",
        "chef": "Harsh Architectural Auditor",
        "skill_dir": "thermo-nuclear-code-quality-review",
        "tags": ["harsh review", "maintainability", "1000 line ceiling", "anti-spaghetti", "structural judo", "architecture audit"],
        "description": "Unusually strict maintainability review. Enforces 1,000-line ceiling, forbids spaghetti conditionals, and seeks structural deletion judo.",
        "related": []
    },
    "unslop": {
        "name": "Unslop Prose",
        "emoji": "🍜",
        "chef": "Human Voice Enforcer",
        "skill_dir": "unslop",
        "tags": ["ai tells", "unslop", "human writing", "no fluff", "active voice", "cut jargon", "anti-bot"],
        "description": "31-rule precision scanner that strips AI tell patterns: superficial -ing, fake ranges, sycophancy, fancy synonyms, and robotic hedging.",
        "related": []
    },
    "create-verification": {
        "name": "Create Verification Skill",
        "emoji": "🔬",
        "chef": "The Grounded Verifier",
        "skill_dir": "pstack/skills/create-verification-skill",
        "tags": ["verification", "test harness", "requirement traceability", "drive", "doctor", "launch", "evidence", "feature map", "prove it works"],
        "description": "Generate a project-local verification skill (.cursor/skills/verify-<app>/) that drives the real app the way a user does with Launch, Doctor, Drive, Evidence, Cleanup, and [REQ-XX] Feature Map.",
        "related": ["maintain-verification", "poteto"]
    },
    "maintain-verification": {
        "name": "Maintain Verification Skill",
        "emoji": "🧪",
        "chef": "The Drift Hunter",
        "skill_dir": "pstack/skills/maintain-verification-skill",
        "tags": ["verify audit", "drift check", "live pass", "feature map upkeep", "doctor check", "evidence"],
        "description": "Periodic upkeep pass that checks source drift, drives every mapped feature live, verifies health with Doctor, and flags product regressions.",
        "related": ["create-verification", "poteto"]
    },
    "no-comments": {
        "name": "No Comments (Comment Sicko)",
        "emoji": "✂️",
        "chef": "Comment Sicko",
        "skill_dir": "pstack/skills/no-comments",
        "tags": ["clean code", "no comments", "comment sicko", "strip ai fluff", "encode constraints", "types over comments"],
        "description": "Eliminate redundant code comments, strip AI commentary, and encode real constraints into types, runtime assertions, or linter rules.",
        "related": ["ponytail", "typescript"]
    },
    "typescript": {
        "name": "TypeScript Best Practices",
        "emoji": "🛡️",
        "chef": "Type Discipline Enforcer",
        "skill_dir": "pstack/skills/typescript-best-practices",
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


def resolve_skill_file(skill_dir: str) -> Path:
    candidates = [
        SKILLS_DIR / skill_dir / "SKILL.md",
        Path.home() / ".gemini" / "config" / "skills" / skill_dir / "SKILL.md",
        Path.home() / "my-agent-skills" / skill_dir / "SKILL.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


def cmd_menu():
    print("\n🍽️  [DoorDash Code Craft Hub] Available Kitchens Menu:\n")
    print(f"{'#':<3} {'Kitchen':<22} {'Chef / Origin':<32} {'Specialty & Vibe'}")
    print("─" * 80)
    for i, (k_id, info) in enumerate(KITCHENS.items(), start=1):
        chef_str = f"{info['emoji']} {info['name']}"
        print(f"{i:<3} {chef_str:<22} {info['chef']:<32} {info['description'][:60]}...")
    print("\n💡 Commands: 'craft-hub inspect <kitchen>' | 'craft-hub order <kitchen> [target]'\n")


def cmd_search(query: str):
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
    if not scored:
        print(f"\n🔍 No kitchens matched '{query}'. Run 'craft-hub menu' to see all 5 available options.\n")
        return

    print(f"\n🔍 [DoorDash Craft Hub] Search Results for '{query}':\n")
    for score, k_id, info in scored:
        print(f"  • {info['emoji']} \033[1m{info['name']}\033[0m (`{k_id}`) — {info['chef']}")
        print(f"    {info['description']}")
        print(f"    Tags: {', '.join(info['tags'][:4])}\n")


def cmd_inspect(kitchen_id: str):
    k_id = kitchen_id.lower().replace("-", "")
    info = KITCHENS.get(kitchen_id.lower()) or KITCHENS.get(k_id)
    if not info:
        # Match by prefix
        for key in KITCHENS:
            if key.startswith(k_id):
                info = KITCHENS[key]
                break

    if not info:
        print(f"❌ Unknown kitchen '{kitchen_id}'. Available: {', '.join(KITCHENS.keys())}")
        sys.exit(1)

    skill_file = resolve_skill_file(info["skill_dir"])
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


def cmd_order(kitchen_id: str, target: str = None):
    k_id = kitchen_id.lower().replace("-", "")

    # Handle "combo" meal: all 5 kitchens!
    if k_id == "combo":
        print("\n🍱 [DoorDash Grand Combo Platter] Ordering from ALL 5 Kitchens!\n" + "=" * 70)
        for sub_k in ["ponytail", "pstack", "poteto", "thermonuclear", "unslop"]:
            cmd_order(sub_k, target)
        return

    info = KITCHENS.get(kitchen_id.lower()) or KITCHENS.get(k_id)
    if not info:
        for key in KITCHENS:
            if key.startswith(k_id):
                info = KITCHENS[key]
                k_id = key
                break

    if not info:
        print(f"❌ Unknown kitchen '{kitchen_id}'. Available: {', '.join(KITCHENS.keys())}, combo")
        sys.exit(1)

    print(f"\n📦 \033[1m[Order Dispatched]\033[0m {info['emoji']} \033[1m{info['name']}\033[0m")
    print(f"   👨‍🍳 Chef: {info['chef']}")
    print(f"   🎯 Lens: {info['description']}")
    print("─" * 70)

    # 1. Resolve Target
    target_text = ""
    is_git_diff = False
    target_desc = ""

    if target and Path(target).is_file():
        target_desc = f"File: {target}"
        target_text = Path(target).read_text(encoding="utf-8", errors="replace")
    elif target and Path(target).is_dir():
        target_desc = f"Directory: {target}"
    else:
        # Default: current git diff
        diff = get_git_diff()
        if diff:
            target_desc = "Current Git Diff (staged + unstaged)"
            target_text = diff
            is_git_diff = True
        else:
            target_desc = "Workspace Codebase"

    print(f"   🔍 Target: {target_desc}")

    # 2. Kitchen-Specific Automated Pre-Checks
    if k_id == "thermonuclear":
        print("\n⚡ [Thermo-Nuclear Automated Checks]:")
        touched = get_git_touched_files() if is_git_diff else ([target] if target and Path(target).is_file() else [])
        if touched:
            for tf in touched:
                try:
                    line_count = len(Path(tf).read_text(encoding="utf-8", errors="replace").splitlines())
                    status = "\033[31m❌ VIOLATION (>1,000 lines)\033[0m" if line_count > 1000 else "\033[32m✅ OK (<1,000 lines)\033[0m"
                    print(f"   • {tf}: {line_count} lines {status}")
                except Exception:
                    pass
        else:
            print("   • No modified files detected for line-count check.")

    elif k_id == "ponytail":
        print("\n⚡ [Ponytail Minimal Diff Checks]:")
        if target_text and is_git_diff:
            added = sum(1 for line in target_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
            deleted = sum(1 for line in target_text.splitlines() if line.startswith("-") and not line.startswith("---"))
            ratio = f"+{added} / -{deleted} (Net: {added - deleted:+d} lines)"
            print(f"   • Diff Volume: {ratio}")
            if added > 150:
                print("   ⚠️  Caution: Large addition (>150 lines). Can this be solved with less new code?")
            else:
                print("   ✅ Diff volume is compact and focused.")
        else:
            print("   • Clean working tree or no diff to calculate delta.")

    elif k_id == "unslop":
        print("\n⚡ [Unslop Automated AI Tell Scan]:")
        findings = scan_unslop(target_text) if target_text else []
        if findings:
            print(f"   ⚠️  Found {len(findings)} potential AI tell pattern(s):")
            for f in findings[:8]:
                print(f"      [Line {f['line']}] {f['label']}: \"{f['match']}\" in: {f['context']}")
            if len(findings) > 8:
                print(f"      ... and {len(findings) - 8} more.")
        else:
            print("   ✅ Clean! No obvious AI tell words detected.")

    elif k_id in ["pstack", "poteto"]:
        print("\n⚡ [pstack / Poteto Architectural Principles Checklist]:")
        print("   1. Model the Domain: Are states modeled as explicit unions/state machines instead of boolean flags?")
        print("   2. Laziness Protocol: Is every line needed? Can dead code be deleted first?")
        print("   3. Verify Artifacts: Is there a concrete check (test, screenshot, command run)?")

    elif "typescript" in k_id or k_id == "ts":
        print("\n⚡ [TypeScript Best Practices Scan]:")
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
            print(f"   • Scanned {len(ts_files)} TypeScript file(s)")
            if any_count > 0:
                print(f"   ⚠️  Found {any_count} loose 'any' annotations! (Prefer 'unknown' or domain types)")
            else:
                print("   ✅ Zero unvalidated 'any' types detected.")
            if as_count > 0:
                print(f"   ⚠️  Found {as_count} 'as' type assertion(s)! (Prefer 'satisfies' or type guards)")
            else:
                print("   ✅ Zero risky 'as' type casts detected.")
        else:
            print("   • No modified .ts/.tsx files found to scan.")

    elif "nocomments" in k_id:
        print("\n⚡ [Comment Sicko Cleanliness Scan]:")
        touched = get_git_touched_files() if is_git_diff else ([target] if target and Path(target).is_file() else [])
        code_files = [f for f in touched if not f.endswith((".md", ".txt", ".json", ".yaml", ".yml"))]
        if code_files:
            for cf in code_files[:5]:
                try:
                    lines = Path(cf).read_text(encoding="utf-8", errors="replace").splitlines()
                    comment_lines = sum(1 for l in lines if re.match(r"^\s*(//|#|/\*|\*)", l))
                    ratio = (comment_lines / len(lines) * 100) if lines else 0
                    print(f"   • {cf}: {comment_lines}/{len(lines)} lines are comments ({ratio:.1f}%)")
                    if ratio > 25:
                        print(f"     ⚠️  High comment ratio ({ratio:.1f}%). Strip obvious code comments; encode constraints into types.")
                except Exception:
                    pass
        else:
            print("   • No modified code files found to audit comments.")

    elif "verification" in k_id or "verify" in k_id:
        print("\n⚡ [Verification Stack Readiness]:")
        has_local_verify = any(Path(p).is_dir() for p in [".cursor/skills", ".gemini/config/skills", "tests", "__tests__"])
        print(f"   • Existing Verification Harness Detected: {'✅ Yes' if has_local_verify else '❌ No'}")
        print("   • Mandatory 5 Invariants: Launch -> Doctor -> Drive -> Evidence -> Cleanup")

    # 3. Output the Authoritative Review Rubric
    skill_file = resolve_skill_file(info["skill_dir"])
    print(f"\n📋 [Review Rubric from {skill_file.name}]:")
    print(f"   Ready to apply {info['name']} standards to {target_desc}.\n")


def main():
    parser = argparse.ArgumentParser(
        prog="craft-hub",
        description="The DoorDash API for Code Craft, Audits, and Rigorous Reviews"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("menu", help="List all 5 kitchens and their specialties")
    sub.add_parser("list", help="Alias for menu")

    p_search = sub.add_parser("search", help="Search kitchens by intent or keyword")
    p_search.add_argument("query", help="Intent query (e.g. 'harsh audit', 'delete bloat')")

    p_inspect = sub.add_parser("inspect", help="Read a kitchen's full rubric and rules")
    p_inspect.add_argument("kitchen", help="Kitchen name (ponytail, pstack, poteto, thermonuclear, unslop)")

    p_order = sub.add_parser("order", help="Dispatch a review order on git diff or target file")
    p_order.add_argument("kitchen", help="Kitchen name (ponytail, pstack, poteto, thermonuclear, unslop, combo)")
    p_order.add_argument("target", nargs="?", default=None, help="Optional file or directory path")

    args = parser.parse_args()
    if args.action in ["menu", "list"]:
        cmd_menu()
    elif args.action == "search":
        cmd_search(args.query)
    elif args.action == "inspect":
        cmd_inspect(args.kitchen)
    elif args.action == "order":
        cmd_order(args.kitchen, args.target)


if __name__ == "__main__":
    main()
