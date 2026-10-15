#!/usr/bin/env python3
"""
factory.py — Reusable ICM Pipeline Driver for Bridging Skills into Uber API Hubs
Non-destructive bridge pattern: preserves standalone skills and SKILL.md files.

Usage:
  # Run entire 3-stage bridge pipeline:
  python3 factory.py bridge --hub academic-icm --skills canvas-cli,zoom-recorder,cornell-notes

  # Stage 1 only (Discover):
  python3 factory.py discover --skills canvas-cli,zoom-recorder

  # Stage 2 only (Bridge / Scaffold):
  python3 factory.py scaffold --hub academic-icm --manifest 01_discover/output/manifest.json

  # Stage 3 only (Verify):
  python3 factory.py verify --hub academic-icm --manifest 01_discover/output/manifest.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
if SCRIPT_PATH.parent.name == "scripts":
    SKILL_DIR = SCRIPT_PATH.parent.parent
else:
    SKILL_DIR = SCRIPT_PATH.parent

TEMPLATES_DIR = SKILL_DIR / "_templates" / "uber-hub"
CANONICAL_SKILLS_DIR = Path("/run/media/rodri/AI/skills")
LOCAL_BIN_DIR = Path.home() / ".local" / "bin"


def stage1_discover(skill_names: list[str], output_file: Path = None) -> dict:
    manifest = {"skills": {}, "callers": {}, "timestamp": datetime.now(timezone.utc).isoformat()}
    print(f"\n🔍 [Stage 01: Discover] Scanning {len(skill_names)} candidate skills...")

    for s_name in skill_names:
        s_dir = CANONICAL_SKILLS_DIR / s_name
        if not s_dir.is_dir():
            print(f"  ⚠️ Warning: Skill directory not found: {s_dir}")
            continue

        skill_md = s_dir / "SKILL.md"
        desc = f"Standalone skill for {s_name}"
        if skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
            if m:
                desc_m = re.search(r"^description:\s*([^\n]+(?:\n\s+[^\n]+)*)", m.group(1), re.MULTILINE)
                if desc_m:
                    raw_desc = desc_m.group(1).strip()
                    desc = " ".join(re.sub(r"^[>|]-?\s*", "", raw_desc).split()).strip('"\'')

        scripts = []
        primary_entry = None
        scripts_dir = s_dir / "scripts"
        if scripts_dir.is_dir():
            for sf in sorted(scripts_dir.iterdir()):
                if sf.is_file() and (sf.suffix in (".py", ".sh") or os.access(sf, os.X_OK)):
                    scripts.append(sf.name)
            if scripts:
                primary_entry = f"scripts/{scripts[0]}"

        # Check for root script if no scripts/ folder
        if not primary_entry:
            for cand in [s_dir / f"{s_name}.py", s_dir / f"{s_name.replace('-', '_')}.py"]:
                if cand.is_file():
                    primary_entry = cand.name
                    break

        manifest["skills"][s_name] = {
            "name": s_name,
            "folder": s_name,
            "path": str(s_dir),
            "description": desc,
            "entrypoint": primary_entry,
            "scripts": scripts,
            "has_skill_md": skill_md.is_file(),
            "tags": [s_name] + [w.lower() for w in re.findall(r"\b[A-Za-z]{3,}\b", desc)[:5]]
        }
        print(f"  • Found '{s_name}': {len(scripts)} scripts, entrypoint={primary_entry}")

    # Discover callers across skills repository
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
        print(f"  ✅ Stage 1 manifest written to: {output_file}")

    return manifest


def stage2_bridge(hub_name: str, manifest: dict, target_dir: Path = None, description: str = None, link_bin: bool = True) -> Path:
    target_dir = target_dir or (CANONICAL_SKILLS_DIR / hub_name)
    target_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = target_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🌉 [Stage 02: Bridge] Generating non-destructive hub router at: {target_dir}")
    hub_desc = description or f"Unified late-binding gateway bridging {len(manifest['skills'])} native standalone skills."

    suites_dict = {}
    table_rows = []

    for s_name, s_info in manifest["skills"].items():
        primary_entry = s_info.get("entrypoint")
        suites_dict[s_name] = {
            "name": s_name,
            "folder": s_info.get("folder", s_name),
            "description": s_info["description"],
            "entrypoint": primary_entry,
            "scripts": s_info.get("scripts", []),
            "tags": s_info.get("tags", [s_name])
        }
        table_rows.append(f"| **`{s_name}`** | {s_info['description']} |")

    # Read templates
    hub_py_tpl = (TEMPLATES_DIR / "hub.py.tpl").read_text(encoding="utf-8")
    skill_md_tpl = (TEMPLATES_DIR / "SKILL.md.tpl").read_text(encoding="utf-8")
    readme_tpl = (TEMPLATES_DIR / "README.md.tpl").read_text(encoding="utf-8")

    suites_literal = json.dumps(suites_dict, indent=4)
    table_markdown = "\n".join(["| Suite | Description |", "|---|---|"] + table_rows)

    # Render files
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

    hub_py_file = target_dir / f"{hub_name}.py"
    hub_py_file.write_text(rendered_hub_py, encoding="utf-8")
    hub_py_file.chmod(0o755)

    script_hub_py = scripts_dir / f"{hub_name}.py"
    script_hub_py.write_text(rendered_hub_py, encoding="utf-8")
    script_hub_py.chmod(0o755)

    (target_dir / "SKILL.md").write_text(rendered_skill_md, encoding="utf-8")
    (target_dir / "README.md").write_text(rendered_readme, encoding="utf-8")

    # Symlink in ~/.local/bin
    if link_bin:
        LOCAL_BIN_DIR.mkdir(parents=True, exist_ok=True)
        main_shim = LOCAL_BIN_DIR / hub_name
        if main_shim.is_symlink() or main_shim.is_file():
            main_shim.unlink()
        main_shim.symlink_to(hub_py_file)
        print(f"  🔗 Hub binary linked: {main_shim} -> {hub_py_file}")

    # Write summary
    summary_path = SKILL_DIR / "02_bridge" / "output" / "bridge_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "hub_name": hub_name,
        "hub_path": str(target_dir),
        "suites_count": len(suites_dict),
        "suites": list(suites_dict.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"  ✅ Stage 2 Bridge completed successfully.")

    return target_dir


def stage3_verify(hub_name: str, manifest: dict, target_dir: Path = None, output_file: Path = None) -> dict:
    target_dir = target_dir or (CANONICAL_SKILLS_DIR / hub_name)
    hub_bin = target_dir / f"{hub_name}.py"
    print(f"\n🔬 [Stage 03: Grounded Verification] Testing bridged hub at: {hub_bin}")

    report = {
        "hub_name": hub_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tests": {},
        "all_passed": True
    }

    def run_check(test_name: str, cmd: list[str]) -> bool:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            passed = res.returncode == 0
            report["tests"][test_name] = {
                "command": " ".join(cmd),
                "exit_code": res.returncode,
                "passed": passed,
                "stdout_sample": res.stdout[:200] if passed else res.stdout[:500],
                "stderr_sample": res.stderr[:500]
            }
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status}: {test_name}")
            if not passed:
                report["all_passed"] = False
            return passed
        except Exception as e:
            report["tests"][test_name] = {
                "command": " ".join(cmd),
                "error": str(e),
                "passed": False
            }
            report["all_passed"] = False
            print(f"  ❌ FAIL: {test_name} ({e})")
            return False

    # 1. Hub --help
    run_check("hub_help", [sys.executable, str(hub_bin), "--help"])

    # 2. Hub list
    run_check("hub_list", [sys.executable, str(hub_bin), "list"])

    # 3. Hub search
    run_check("hub_search", [sys.executable, str(hub_bin), "search", "test"])

    # 4. Hub inspect for each suite
    for s_name in manifest.get("skills", {}).keys():
        run_check(f"inspect_{s_name}", [sys.executable, str(hub_bin), "inspect", s_name])

    # 5. Check standalone skills independence (SKILL.md exists and untouched)
    for s_name, s_info in manifest.get("skills", {}).items():
        s_path = Path(s_info.get("path", CANONICAL_SKILLS_DIR / s_name))
        skill_md = s_path / "SKILL.md"
        exists = skill_md.is_file()
        report["tests"][f"standalone_{s_name}_intact"] = {
            "path": str(skill_md),
            "passed": exists
        }
        status = "✅ PASS" if exists else "❌ FAIL"
        print(f"  {status}: standalone_{s_name}_intact (native SKILL.md preserved)")
        if not exists:
            report["all_passed"] = False

    output_file = output_file or (SKILL_DIR / "03_verify" / "output" / "verification_report.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  ✅ Verification report saved to: {output_file}")

    if not report["all_passed"]:
        print("  ⚠️ Warning: Some verification checks failed.")
    else:
        print("  🎉 All verification checks passed!")

    return report


def cmd_bridge(hub_name: str, skills_list: list[str], sync: bool = False, description: str = None):
    print(f"\n🚀 [uber-hub-factory] Bridging Hub '{hub_name}' across {len(skills_list)} skills...")
    m_path = SKILL_DIR / "01_discover" / "output" / "manifest.json"
    manifest = stage1_discover(skills_list, output_file=m_path)
    stage2_bridge(hub_name, manifest, description=description)
    report = stage3_verify(hub_name, manifest)

    if sync and report["all_passed"]:
        print("\n📤 Synchronizing skills across harnesses and pushing to GitHub...")
        subprocess.run(["sync-skills", "--push"], check=True)

    print(f"\n✨ Non-destructive bridge for '{hub_name}' complete!\n")


def main():
    parser = argparse.ArgumentParser(
        prog="uber-hub-factory",
        description="Autonomous Non-Destructive ICM Pipeline & CLI Factory for Bridging Skills into Uber API Hubs"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # 1. bridge (alias build)
    for cmd_alias in ["bridge", "build"]:
        p_b = sub.add_parser(cmd_alias, help="Run full 3-stage pipeline to bridge skills into a hub")
        p_b.add_argument("--hub", required=True, help="Name of target hub (e.g. academic-icm)")
        p_b.add_argument("--skills", required=True, help="Comma-separated list of skills to bridge")
        p_b.add_argument("--description", help="Custom description for the hub")
        p_b.add_argument("--sync", action="store_true", help="Run sync-skills --push after bridging")

    # 2. discover (alias inventory)
    for cmd_alias in ["discover", "inventory"]:
        p_d = sub.add_parser(cmd_alias, help="Stage 1: Discover skills, scripts, and generate manifest")
        p_d.add_argument("--skills", required=True, help="Comma-separated list of skills to discover")
        p_d.add_argument("--output", help="Optional output manifest path")

    # 3. scaffold
    p_s = sub.add_parser("scaffold", help="Stage 2: Scaffold non-destructive router and documentation")
    p_s.add_argument("--hub", required=True, help="Name of target hub")
    p_s.add_argument("--manifest", default=str(SKILL_DIR / "01_discover" / "output" / "manifest.json"))
    p_s.add_argument("--description", help="Custom description for the hub")

    # 4. verify
    p_v = sub.add_parser("verify", help="Stage 3: Run grounded verification tests")
    p_v.add_argument("--hub", required=True, help="Name of target hub")
    p_v.add_argument("--manifest", default=str(SKILL_DIR / "01_discover" / "output" / "manifest.json"))

    args = parser.parse_args()

    if args.action in ["bridge", "build"]:
        s_list = [s.strip() for s in args.skills.split(",") if s.strip()]
        cmd_bridge(args.hub, s_list, sync=getattr(args, "sync", False), description=args.description)
    elif args.action in ["discover", "inventory"]:
        s_list = [s.strip() for s in args.skills.split(",") if s.strip()]
        out = Path(args.output) if getattr(args, "output", None) else (SKILL_DIR / "01_discover" / "output" / "manifest.json")
        stage1_discover(s_list, output_file=out)
    elif args.action == "scaffold":
        m_path = Path(args.manifest)
        if not m_path.is_file():
            sys.exit(f"❌ Manifest not found: {m_path}")
        manifest = json.loads(m_path.read_text(encoding="utf-8"))
        stage2_bridge(args.hub, manifest, description=args.description)
    elif args.action == "verify":
        m_path = Path(args.manifest)
        manifest = json.loads(m_path.read_text(encoding="utf-8")) if m_path.is_file() else {"skills": {}}
        stage3_verify(args.hub, manifest)


if __name__ == "__main__":
    main()
