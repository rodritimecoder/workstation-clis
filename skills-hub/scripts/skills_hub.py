#!/usr/bin/env python3
"""
skills_hub.py — Meta-Tool Discovery and Execution Gateway for AI Agent Skills
Implements the Uber API / Late-Binding Pattern: Search, Inspect, and Run skills dynamically.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CANDIDATE_PATHS = [
    Path("/run/media/rodri/AI/skills"),
    Path.home() / "my-agent-skills",
    Path.home() / ".gemini" / "config" / "skills",
    Path.cwd() / ".agents" / "skills",
    Path.home() / "workstation-clis",
]


def resolve_skills_dir() -> Path:
    for p in CANDIDATE_PATHS:
        if p.is_dir() and any((p / s / "SKILL.md").is_file() for s in p.iterdir() if s.is_dir()):
            return p
    return Path.home() / "my-agent-skills"


def load_all_skills():
    root = resolve_skills_dir()
    skills = {}
    if not root.is_dir():
        return skills

    for item in sorted(root.iterdir()):
        skill_md = item / "SKILL.md"
        if item.is_dir() and skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8")
            name = item.name
            desc = "No description provided."
            match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
            if match:
                fm = match.group(1)
                name_m = re.search(r"^name:\s*([^\n]+)", fm, re.MULTILINE)
                if name_m:
                    name = name_m.group(1).strip()
                desc_m = re.search(r"^description:\s*([^\n]+(?:\n\s+[^\n]+)*)", fm, re.MULTILINE)
                if desc_m:
                    raw_desc = desc_m.group(1).strip()
                    # Strip leading YAML block scalars > or >- or |-
                    raw_desc = re.sub(r"^[>|]-?\s*", "", raw_desc)
                    # Flatten newlines and whitespace
                    desc = " ".join(raw_desc.split()).strip('"\'')

            skills[name] = {
                "name": name,
                "dir_name": item.name,
                "path": str(item),
                "description": desc,
                "md_path": str(skill_md),
                "full_text": content,
            }
    return skills


def cmd_list(as_json=False):
    skills = load_all_skills()
    if as_json:
        data = [{"name": s["name"], "dir": s["dir_name"], "description": s["description"]} for s in skills.values()]
        print(json.dumps(data, indent=2))
        return

    print(f"\n📦 [Skills Hub] Registered Agent Skills ({len(skills)} found):")
    print(f"{'Skill Name':<28} │ {'Description'}")
    print("─" * 29 + "┼" + "─" * 50)
    for s in skills.values():
        clean_desc = s["description"][:65] + "..." if len(s["description"]) > 65 else s["description"]
        print(f"{s['name']:<28} │ {clean_desc}")


def cmd_search(query: str):
    skills = load_all_skills()
    q_tokens = query.lower().split()
    scored = []

    for s in skills.values():
        score = 0
        name_lower = s["name"].lower()
        desc_lower = s["description"].lower()
        text_lower = s["full_text"].lower()

        for t in q_tokens:
            if t in name_lower:
                score += 5
            if t in desc_lower:
                score += 3
            if t in text_lower:
                score += 1

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    print(f"\n🔍 [Skills Hub] Search results for '{query}':")
    if not scored:
        print("  (No matching skills found)")
        return

    for score, s in scored[:5]:
        print(f"\n  • 🎯 {s['name']} (relevance: {score})")
        print(f"    {s['description']}")
        print(f"    Path: {s['path']}")


def cmd_inspect(skill_name: str):
    skills = load_all_skills()
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found. Run 'skills-hub list' to view available skills.")

    print(f"\n📖 [Skills Hub] Inspecting skill: {target['name']}\n")
    content = Path(target["md_path"]).read_text(encoding="utf-8")
    # Print content stripping raw frontmatter for clean reading
    clean_content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
    print(clean_content)


def cmd_run(skill_name: str, extra_args: list):
    skills = load_all_skills()
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    skill_path = Path(target["path"])
    scripts_dir = skill_path / "scripts"

    # 1. Look for executable scripts in scripts/
    candidates = []
    if scripts_dir.is_dir():
        for f in scripts_dir.iterdir():
            if f.is_file() and (f.suffix in (".py", ".sh") or os.access(f, os.X_OK)):
                candidates.append(f)

    # 2. Check ~/.local/bin for exact matches
    local_bin_match = Path.home() / ".local" / "bin" / target["name"]
    if local_bin_match.is_file() and os.access(local_bin_match, os.X_OK):
        cmd = [str(local_bin_match)] + extra_args
    elif candidates:
        primary = candidates[0]
        for c in candidates:
            if target["name"].replace("-", "_") in c.name or target["name"] in c.name:
                primary = c
                break
        if primary.suffix == ".py":
            cmd = [sys.executable, str(primary)] + extra_args
        elif primary.suffix == ".sh":
            cmd = ["bash", str(primary)] + extra_args
        else:
            cmd = [str(primary)] + extra_args
    else:
        sys.exit(f"❌ Error: No runnable script found for skill '{skill_name}' in {scripts_dir}")

    print(f"🚀 [Skills Hub] Executing: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skills Hub — Meta-Tool Discovery and Execution Gateway")
    sub = parser.add_subparsers(dest="action", required=True)

    p_list = sub.add_parser("list", help="List all registered skills")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    p_search = sub.add_parser("search", help="Search skills by keyword or intent")
    p_search.add_argument("query", help="Search query")

    p_inspect = sub.add_parser("inspect", help="Inspect a skill's full documentation and commands")
    p_inspect.add_argument("skill", help="Name of skill to inspect")

    p_run = sub.add_parser("run", help="Execute a skill command dynamically")
    p_run.add_argument("skill", help="Name of skill to run")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the skill")

    args = parser.parse_args()
    if args.action == "list":
        cmd_list(as_json=args.json)
    elif args.action == "search":
        cmd_search(args.query)
    elif args.action == "inspect":
        cmd_inspect(args.skill)
    elif args.action == "run":
        cmd_run(args.skill, args.args)
