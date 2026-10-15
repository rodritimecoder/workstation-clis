#!/usr/bin/env python3
"""
factory.py — Reusable ICM Pipeline Driver for Consolidating Skills into Uber API Hubs

Usage:
  # Run entire pipeline to consolidate skills into a new hub:
  python3 factory.py build --hub academic-hub --skills canvas-cli,zoom-recorder,cornell-notes

  # Stage 1 only (Inventory):
  python3 factory.py inventory --skills canvas-cli,zoom-recorder

  # Stage 2 only (Scaffold):
  python3 factory.py scaffold --hub academic-hub --manifest 01_inventory/output/manifest.json

  # Stage 3 only (Shims):
  python3 factory.py shim --hub academic-hub --manifest 01_inventory/output/manifest.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "_templates" / "uber-hub"
CANONICAL_SKILLS_DIR = Path("/run/media/rodri/AI/skills")
LOCAL_BIN_DIR = Path.home() / ".local" / "bin"


def stage1_inventory(skill_names: list[str], output_file: Path = None) -> dict:
    manifest = {"skills": {}, "callers": {}}
    for s_name in skill_names:
        s_dir = CANONICAL_SKILLS_DIR / s_name
        if not s_dir.is_dir():
            print(f"⚠️ Warning: Source skill directory not found: {s_dir}")
            continue

        skill_md = s_dir / "SKILL.md"
        desc = "No description provided."
        if skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
            if m:
                desc_m = re.search(r"^description:\s*([^\n]+(?:\n\s+[^\n]+)*)", m.group(1), re.MULTILINE)
                if desc_m:
                    raw_desc = desc_m.group(1).strip()
                    desc = " ".join(re.sub(r"^[>|]-?\s*", "", raw_desc).split()).strip('"\'')

        scripts = []
        scripts_dir = s_dir / "scripts"
        if scripts_dir.is_dir():
            for sf in scripts_dir.iterdir():
                if sf.is_file() and (sf.suffix in (".py", ".sh") or os.access(sf, os.X_OK)):
                    scripts.append(sf.name)

        manifest["skills"][s_name] = {
            "name": s_name,
            "path": str(s_dir),
            "description": desc,
            "scripts": scripts,
            "has_skill_md": skill_md.is_file()
        }

    # Search callers across the skills repo
    for s_name in skill_names:
        try:
            res = subprocess.run(
                ["git", "-C", str(CANONICAL_SKILLS_DIR), "grep", "-l", s_name],
                capture_output=True, text=True
            )
            if res.returncode == 0:
                callers = [f for f in res.stdout.splitlines() if not f.startswith(s_name + "/")]
                manifest["callers"][s_name] = callers
        except Exception:
            manifest["callers"][s_name] = []

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"✅ Stage 1 Inventory written to: {output_file}")

    return manifest


def stage2_scaffold(hub_name: str, manifest: dict, target_dir: Path = None, description: str = None) -> Path:
    target_dir = target_dir or (CANONICAL_SKILLS_DIR / hub_name)
    target_dir.mkdir(parents=True, exist_ok=True)
    suites_dir = target_dir / "suites"
    suites_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = target_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    hub_desc = description or f"Unified late-binding gateway uniting {len(manifest['skills'])} suites."

    suites_dict = {}
    table_rows = []

    for s_name, s_info in manifest["skills"].items():
        src_path = Path(s_info["path"])
        dest_suite_dir = suites_dir / s_name
        dest_suite_dir.mkdir(parents=True, exist_ok=True)

        # Copy assets
        for item in src_path.iterdir():
            if item.name in ("__pycache__", ".venv", ".git"):
                continue
            dest_item = dest_suite_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

        # Inlining: Rename any nested SKILL.md to rubric.md (zero harness registration bloat!)
        for smd in dest_suite_dir.rglob("SKILL.md"):
            rubric_path = smd.parent / "rubric.md"
            smd.rename(rubric_path)

        primary_entry = f"suites/{s_name}/scripts/{s_info['scripts'][0]}" if s_info["scripts"] else None
        suites_dict[s_name] = {
            "name": s_name,
            "description": s_info["description"],
            "rubric_path": f"{s_name}/rubric.md",
            "entrypoint": primary_entry,
            "scripts": s_info["scripts"],
            "tags": [s_name]
        }
        table_rows.append(f"| **`{s_name}`** | {s_info['description']} |")

    # Read templates
    hub_py_tpl = (TEMPLATES_DIR / "hub.py.tpl").read_text(encoding="utf-8")
    skill_md_tpl = (TEMPLATES_DIR / "SKILL.md.tpl").read_text(encoding="utf-8")
    readme_tpl = (TEMPLATES_DIR / "README.md.tpl").read_text(encoding="utf-8")

    suites_literal = json.dumps(suites_dict, indent=4)
    table_markdown = "\n".join(["| Suite | Description |", "|---|---|"] + table_rows)

    # Render hub_cli.py
    rendered_hub_py = hub_py_tpl.replace("{HUB_NAME}", hub_name)\
                                .replace("{HUB_NAME_UPPER}", hub_name.upper().replace("-", " "))\
                                .replace("{HUB_DESCRIPTION}", hub_desc)\
                                .replace("{SUITES_DICT_LITERAL}", suites_literal)

    rendered_skill_md = skill_md_tpl.replace("{HUB_NAME}", hub_name)\
                                    .replace("{HUB_DESCRIPTION}", hub_desc)\
                                    .replace("{SUITES_MARKDOWN_TABLE}", table_markdown)

    rendered_readme = readme_tpl.replace("{HUB_NAME}", hub_name)\
                                .replace("{HUB_DESCRIPTION}", hub_desc)\
                                .replace("{SUITE_COUNT}", str(len(suites_dict)))\
                                .replace("{SUITES_MARKDOWN_TABLE}", table_markdown)

    # Write files
    (target_dir / f"{hub_name}.py").write_text(rendered_hub_py, encoding="utf-8")
    os.chmod(target_dir / f"{hub_name}.py", 0o755)

    (scripts_dir / f"{hub_name}.py").write_text(rendered_hub_py, encoding="utf-8")
    os.chmod(scripts_dir / f"{hub_name}.py", 0o755)

    (target_dir / "SKILL.md").write_text(rendered_skill_md, encoding="utf-8")
    (target_dir / "README.md").write_text(rendered_readme, encoding="utf-8")

    print(f"✅ Stage 2 Hub Scaffolding complete at: {target_dir}")
    return target_dir


def stage3_shims(hub_name: str, manifest: dict):
    LOCAL_BIN_DIR.mkdir(parents=True, exist_ok=True)
    hub_bin = CANONICAL_SKILLS_DIR / hub_name / f"{hub_name}.py"

    # Link main hub
    main_shim = LOCAL_BIN_DIR / hub_name
    if main_shim.is_symlink() or main_shim.is_file():
        main_shim.unlink()
    main_shim.symlink_to(hub_bin)
    print(f"🔗 Main hub symlinked: {main_shim} -> {hub_bin}")

    # Generate shims for child skills
    for s_name in manifest["skills"].keys():
        shim_path = LOCAL_BIN_DIR / s_name
        if shim_path.is_symlink() or shim_path.is_file():
            shim_path.unlink()
        shim_content = f"#!/usr/bin/env bash\nexec {hub_name} run {s_name} \"$@\"\n"
        shim_path.write_text(shim_content, encoding="utf-8")
        shim_path.chmod(0o755)
        print(f"🔗 Legacy shim created: {shim_path} -> {hub_name} run {s_name}")


def stage4_verify_and_purge(hub_name: str, manifest: dict, purge: bool = False, sync: bool = False):
    print("\n🔬 [Grounded Verification]")
    hub_bin = CANONICAL_SKILLS_DIR / hub_name / f"{hub_name}.py"
    res = subprocess.run([sys.executable, str(hub_bin), "list"], capture_output=True, text=True)
    if res.returncode == 0:
        print("  ✅ Hub list command verified successfully.")
    else:
        sys.exit(f"❌ Verification failed for {hub_name} list:\n{res.stderr}")

    if purge:
        print("\n🧹 Purging obsolete standalone skill folders...")
        for s_name in manifest["skills"].keys():
            s_dir = CANONICAL_SKILLS_DIR / s_name
            if s_dir.is_dir() and s_name != hub_name:
                shutil.rmtree(s_dir)
                print(f"  🗑️ Deleted: {s_dir}")

    if sync:
        print("\n📤 Synchronizing across harnesses and pushing to GitHub...")
        subprocess.run(["sync-skills", "--push"], check=True)


def cmd_build(hub_name: str, skills_list: list[str], purge: bool = False, sync: bool = False, description: str = None):
    print(f"\n🚀 [uber-hub-factory] Building Hub '{hub_name}' from {len(skills_list)} skills...\n")
    m_path = SKILL_DIR / "01_inventory" / "output" / "manifest.json"
    manifest = stage1_inventory(skills_list, output_file=m_path)
    stage2_scaffold(hub_name, manifest, description=description)
    stage3_shims(hub_name, manifest)
    stage4_verify_and_purge(hub_name, manifest, purge=purge, sync=sync)
    print(f"\n✨ Hub '{hub_name}' consolidation complete!\n")


def main():
    parser = argparse.ArgumentParser(
        prog="uber-hub-factory",
        description="Autonomous ICM Pipeline & Factory for Consolidating Skills into Uber API Hubs"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_build = sub.add_parser("build", help="Run full pipeline to consolidate skills into a hub")
    p_build.add_argument("--hub", required=True, help="Name of target hub (e.g. academic-hub)")
    p_build.add_argument("--skills", required=True, help="Comma-separated list of skills to consolidate")
    p_build.add_argument("--description", help="Custom description for the hub")
    p_build.add_argument("--purge", action="store_true", help="Purge original standalone folders after verifying")
    p_build.add_argument("--sync", action="store_true", help="Run sync-skills --push after building")

    p_inv = sub.add_parser("inventory", help="Stage 1: Scan skills and generate manifest")
    p_inv.add_argument("--skills", required=True, help="Comma-separated list of skills to scan")

    args = parser.parse_args()
    if args.action == "build":
        s_list = [s.strip() for s in args.skills.split(",") if s.strip()]
        cmd_build(args.hub, s_list, purge=args.purge, sync=args.sync, description=args.description)
    elif args.action == "inventory":
        s_list = [s.strip() for s in args.skills.split(",") if s.strip()]
        stage1_inventory(s_list, output_file=SKILL_DIR / "01_inventory" / "output" / "manifest.json")


if __name__ == "__main__":
    main()
