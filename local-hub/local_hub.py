#!/usr/bin/env python3
"""
local_hub.py — Unified Local Inference Hub and Skill Execution Gateway for Workstation

Unifies all local Dual-GPU inference services into a single tool:
  • local-hub llm     — Qwen3.6-35B Genesis (:8080)
  • local-hub ocr     — LightOnOCR-3-1B Vision OCR (:8085)
  • local-hub decide  — Imajev-4B / JPT-4B Calibrated Decisions (:8083)
  • local-hub asr     — audio.cpp Nemotron-3.5 Speech-to-Text (:8081)
  • local-hub status  — Live health check on :8080–:8090 endpoints

Also provides the Uber OmniMCP / aifx late-binding skill discovery protocol:
  • local-hub search  — Intent search across all workstation skills
  • local-hub run     — Response projection & disk buffering for any skill
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
if SCRIPT_PATH.parent.name == "scripts":
    SKILL_DIR = SCRIPT_PATH.parent.parent
else:
    SKILL_DIR = SCRIPT_PATH.parent

SCRIPTS_DIR = SKILL_DIR / "scripts"
VENV_PYTHON = SKILL_DIR / ".venv" / "bin" / "python"

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


def get_python_for_script(script_path: Path) -> str:
    """Return python executable to run script, preferring local venv if available."""
    if VENV_PYTHON.is_file() and os.access(VENV_PYTHON, os.X_OK):
        return str(VENV_PYTHON)
    return sys.executable


def exec_internal_script(script_name: str, args: list[str]):
    """Execute an internal local-hub engine script."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.is_file():
        sys.exit(f"❌ Error: Internal engine script not found at {script_path}")
    
    python_bin = get_python_for_script(script_path)
    cmd = [python_bin, str(script_path)] + args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def _parse_skill_entry(item: Path, skill_md: Path, status: str = "active") -> dict:
    content = skill_md.read_text(encoding="utf-8", errors="replace")
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
            raw_desc = re.sub(r"^[>|]-?\s*", "", raw_desc)
            desc = " ".join(raw_desc.split()).strip('"\'')

    scripts_dir = item / "scripts"
    scripts = []
    if scripts_dir.is_dir():
        for sf in scripts_dir.iterdir():
            if sf.is_file() and (sf.suffix in (".py", ".sh") or os.access(sf, os.X_OK)):
                scripts.append(sf.name)

    return {
        "name": name,
        "dir_name": item.name,
        "path": str(item),
        "md_path": str(skill_md),
        "description": desc,
        "scripts": scripts,
        "status": status,
    }


def load_all_skills(include_sidelined: bool = False):
    root = resolve_skills_dir()
    skills = {}
    if not root.is_dir():
        return skills

    for item in sorted(root.iterdir()):
        if item.name in ("glitch-cat", "archived", "docs", "launchers"):
            continue
        skill_md = item / "SKILL.md"
        if item.is_dir() and skill_md.is_file():
            s = _parse_skill_entry(item, skill_md, status="active")
            skills[s["name"]] = s

    if include_sidelined:
        for sub in ("glitch-cat", "archived"):
            subdir = root / sub
            if subdir.is_dir():
                for item in sorted(subdir.iterdir()):
                    skill_md = item / "SKILL.md"
                    if item.is_dir() and skill_md.is_file():
                        s = _parse_skill_entry(item, skill_md, status=sub)
                        if s["name"] not in skills and item.name not in skills:
                            skills[s["name"]] = s
    return skills


def cmd_list(as_json: bool = False, show_all: bool = False):
    skills = load_all_skills(include_sidelined=show_all)
    if as_json:
        print(json.dumps(list(skills.values()), indent=2))
        return

    active = {k: v for k, v in skills.items() if v.get("status") == "active"}
    dormant = {k: v for k, v in skills.items() if v.get("status") != "active"}

    print(f"\n📦 [Local Hub Registry] Found {len(active)} Active Skills:\n")
    for name, s in sorted(active.items()):
        scripts_info = f" ({len(s['scripts'])} scripts)" if s['scripts'] else ""
        print(f"  • {name:<30} {scripts_info}")
        print(f"    {s['description'][:100]}...\n")

    if show_all and dormant:
        print(f"📦 [Sidelined & Archived Registry] Found {len(dormant)} Dormant Skills:\n")
        for name, s in sorted(dormant.items()):
            scripts_info = f" ({len(s['scripts'])} scripts)" if s['scripts'] else ""
            status_tag = f"[{s.get('status').upper()}]"
            print(f"  • {name:<30} {status_tag} {scripts_info}")
            print(f"    {s['description'][:100]}...\n")
    elif not show_all:
        dormant_count = len(load_all_skills(include_sidelined=True)) - len(active)
        if dormant_count > 0:
            print(f"💡 Tip: {dormant_count} skills are currently sidelined. Run 'local-hub list --all' to inspect them.\n")


def cmd_search(query: str, as_json: bool = False, search_all: bool = False):
    skills = load_all_skills(include_sidelined=search_all)
    q_tokens = query.lower().split()
    scored = []

    for name, s in skills.items():
        score = 0
        md_content = Path(s["md_path"]).read_text(encoding="utf-8", errors="replace").lower()
        desc = s["description"].lower()
        n = name.lower()

        for t in q_tokens:
            if t in n:
                score += 10
            if t in desc:
                score += 5
            score += min(md_content.count(t), 10)

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [s for _, s in scored]

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print(f"\n🔍 [Uber Protocol Search] Intent: '{query}'\n")
    if not scored:
        # Check if query matches dormant skills
        dormant_skills = load_all_skills(include_sidelined=True)
        dormant_scored = []
        for name, s in dormant_skills.items():
            if s.get("status") == "active":
                continue
            sc = 0
            md_content = Path(s["md_path"]).read_text(encoding="utf-8", errors="replace").lower()
            desc = s["description"].lower()
            n = name.lower()
            for t in q_tokens:
                if t in n:
                    sc += 10
                if t in desc:
                    sc += 5
                sc += min(md_content.count(t), 10)
            if sc > 0:
                dormant_scored.append((sc, s))

        if dormant_scored:
            dormant_scored.sort(key=lambda x: x[0], reverse=True)
            print("  No active skills matched, but found matching sidelined skills:")
            for sc, s in dormant_scored[:5]:
                print(f"  • 💤 {s['name']} (relevance: {sc}) [{s.get('status').upper()}]")
                print(f"    {s['description']}")
                print(f"    Path: {s['path']}")
                print(f"    Reactivate: ln -s {s['path']} /run/media/rodri/AI/skills/{s['dir_name']}\n")
        else:
            print("  No matching skills found.")
        return

    for score, s in scored[:6]:
        status_tag = f" [{s.get('status').upper()}]" if s.get("status") != "active" else ""
        print(f"  • 🎯 {s['name']}{status_tag} (relevance: {score})")
        print(f"    {s['description']}")
        if s["scripts"]:
            print(f"    Tools/Scripts: {', '.join(s['scripts'])}")
        print(f"    Inspect: local-hub inspect {s['name']}\n")


def cmd_tools(skill_name: str):
    skills = load_all_skills(include_sidelined=True)
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    status_tag = f" [{target.get('status').upper()}]" if target.get("status") != "active" else ""
    print(f"\n🛠️  [Available Tools] Skill: {target['name']}{status_tag}")
    print(f"   Directory: {target['path']}\n")
    if not target["scripts"]:
        print("   No executable scripts found in scripts/.")
        return

    for sc in target["scripts"]:
        print(f"   - {sc}")
    print(f"\n   Run via: local-hub run {target['name']} <script_name> [args...]")


def cmd_inspect(skill_name: str):
    skills = load_all_skills(include_sidelined=True)
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    status_tag = f" [{target.get('status').upper()}]" if target.get("status") != "active" else ""
    print(f"\n📖 [Uber Schema & Contract] {target['name']}{status_tag}\n")
    if target.get("status") != "active":
        print(f"ℹ️  Status: Currently {target.get('status').upper()} (sidelined to minimize prompt tokens).")
        print(f"   Path: {target['path']}")
        print(f"   Reactivate anytime with: ln -s {target['path']} /run/media/rodri/AI/skills/{target['dir_name']}\n")
    content = Path(target["md_path"]).read_text(encoding="utf-8")
    clean_content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
    print(clean_content)


def apply_response_projection(raw_output: str, project_fields: list = None, jq_expr: str = None) -> str:
    if not raw_output.strip():
        return raw_output

    if jq_expr and shutil.which("jq"):
        try:
            p = subprocess.run(["jq", jq_expr], input=raw_output, text=True, capture_output=True)
            if p.returncode == 0:
                return p.stdout.strip()
        except Exception:
            pass

    if project_fields:
        try:
            data = json.loads(raw_output)
            if isinstance(data, dict):
                filtered = {k: v for k, v in data.items() if k in project_fields}
                return json.dumps(filtered, indent=2)
            elif isinstance(data, list):
                filtered = [
                    {k: v for k, v in item.items() if k in project_fields} if isinstance(item, dict) else item
                    for item in data
                ]
                return json.dumps(filtered, indent=2)
        except Exception:
            pass

    return raw_output


def cmd_run(skill_name: str, extra_args: list, out_path: str = None, project_fields: str = None, jq_expr: str = None):
    # Native shortcuts for local-hub internal engines
    if skill_name in ("llm", "llm-cli"):
        exec_internal_script("llm_client.py", extra_args)
    elif skill_name in ("ocr", "ocr-cli"):
        exec_internal_script("ocr.py", extra_args)
    elif skill_name in ("decide", "jev", "jev-cli"):
        exec_internal_script("decide.py", extra_args)
    elif skill_name in ("asr", "audiocpp-asr"):
        exec_internal_script("asr.py", extra_args)

    skills = load_all_skills(include_sidelined=True)
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    skill_path = Path(target["path"])
    scripts_dir = skill_path / "scripts"

    candidates = []
    if scripts_dir.is_dir():
        for f in scripts_dir.iterdir():
            if f.is_file() and (f.suffix in (".py", ".sh") or os.access(f, os.X_OK)):
                candidates.append(f)

    local_bin_match = Path.home() / ".local" / "bin" / target["name"]
    if local_bin_match.is_file() and os.access(local_bin_match, os.X_OK):
        cmd = [str(local_bin_match)] + extra_args
    elif candidates:
        primary = candidates[0]
        if extra_args and extra_args[0] in [c.name for c in candidates]:
            primary = [c for c in candidates if c.name == extra_args[0]][0]
            extra_args = extra_args[1:]
        
        if primary.suffix == ".py":
            cmd = [sys.executable, str(primary)] + extra_args
        else:
            cmd = [str(primary)] + extra_args
    else:
        sys.exit(f"❌ Error: No executable command found for '{skill_name}'.")

    if out_path or project_fields or jq_expr:
        res = subprocess.run(cmd, capture_output=True, text=True)
        combined = res.stdout
        if res.stderr:
            combined += ("\n" + res.stderr if combined else res.stderr)

        fields = [f.strip() for f in project_fields.split(",")] if project_fields else None
        projected = apply_response_projection(combined, fields, jq_expr)

        if out_path:
            p = Path(out_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(projected, encoding="utf-8")
            print(f"💾 Output buffered to: {p}")
            print(f"📊 Projected summary: {len(projected.splitlines())} lines ({len(projected)} bytes)")
        else:
            print(projected)

        sys.exit(res.returncode)
    else:
        p = subprocess.run(cmd)
        sys.exit(p.returncode)


def get_tailscale_info():
    node_dns = None
    node_ip = None
    try:
        p = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True)
        if p.returncode == 0:
            data = json.loads(p.stdout)
            self_node = data.get("Self", {})
            node_dns = self_node.get("DNSName", "").rstrip(".")
            ips = self_node.get("TailscaleIPs", [])
            node_ip = ips[0] if ips else None
    except Exception:
        pass
    return node_dns, node_ip


def check_port_open(port: int, timeout: float = 0.5) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def cmd_status(as_json: bool = False):
    ts_dns, ts_ip = get_tailscale_info()
    services = [
        {"port": 4000, "name": "LiteLLM Dynamic Gateway", "role": "Multi-model proxy & failover"},
        {"port": 8000, "name": "llama-swap Controller", "role": "Model hot-swapper (<32GB VRAM)"},
        {"port": 8080, "name": "Genesis 35B Primary LLM", "role": "Dual-GPU Flagship Coder (:8080)"},
        {"port": 8081, "name": "audio.cpp Nemotron ASR & TTS", "role": "Streaming speech-to-text / TTS"},
        {"port": 8082, "name": "EmbeddingGemma-2 768d Embeddings", "role": "Multimodal text & image vector search"},
        {"port": 8083, "name": "OneJev1.5-4B Decision Gating", "role": "Premier calibrated multimodal decisions"},
        {"port": 8084, "name": "CrispEmbed Scene-Text OCR", "role": "Ultra-fast text detection"},
        {"port": 8085, "name": "LightOnOCR Flagship Document OCR", "role": "#1 document and slide OCR"},
        {"port": 8088, "name": "DeskForge Visual GUI Grounding", "role": "Computer-use visual coordinates"},
        {"port": 8090, "name": "JPT-4B Decision Engine", "role": "System One gating with vision"},
        {"port": 9222, "name": "Chromium CDP DevTools", "role": "Direct WebSocket/CDP for fast-cdp"},
        {"port": 3010, "name": "KasmVNC Browser Web Desktop", "role": "Headless browser sandbox"},
    ]

    results = []
    for s in services:
        is_open = check_port_open(s["port"])
        status = "ONLINE" if is_open else "OFFLINE"
        tailscale_url = f"https://{ts_dns}:{s['port']}" if ts_dns else f"http://100.x.x.x:{s['port']}"
        local_url = f"http://127.0.0.1:{s['port']}"
        results.append({
            "service": s["name"],
            "port": s["port"],
            "status": status,
            "local_url": local_url,
            "tailscale_url": tailscale_url,
            "role": s["role"]
        })

    if as_json:
        print(json.dumps({"tailscale_node": ts_dns, "tailscale_ip": ts_ip, "services": results}, indent=2))
        return

    print("\n🌐 [Workstation Inference & Tailscale Mesh]")
    print(f"   Node DNS: {ts_dns or 'Offline'}")
    print(f"   Node IP:  {ts_ip or 'Offline'}")
    print("\n   " + f"{'SERVICE':<34} │ {'STATUS':<10} │ {'LOCAL ENDPOINT':<24} │ {'TAILSCALE HTTPS ENDPOINT'}")
    print("   " + "─" * 35 + "┼" + "─" * 12 + "┼" + "─" * 26 + "┼" + "─" * 40)
    for r in results:
        status_icon = "🟢 ONLINE " if r["status"] == "ONLINE" else "⚪ OFFLINE"
        print(f"   {r['service']:<34} │ {status_icon:<10} │ {r['local_url']:<24} │ {r['tailscale_url']}")

    print("\n💡 Tip: Run `tailscale-ops serve-mesh` to expose all services over private Tailscale HTTPS.")


def main():
    if len(sys.argv) > 1:
        subcmd = sys.argv[1]
        if subcmd == "llm":
            exec_internal_script("llm_client.py", sys.argv[2:])
        elif subcmd == "ocr":
            exec_internal_script("ocr.py", sys.argv[2:])
        elif subcmd in ("decide", "jev"):
            exec_internal_script("decide.py", sys.argv[2:])
        elif subcmd == "asr":
            exec_internal_script("asr.py", sys.argv[2:])
        elif subcmd in ("cdp", "browser"):
            fast_cdp = shutil.which("fast-cdp") or "/run/media/rodri/AI/skills/hybrid-browser/scripts/fast-cdp"
            res = subprocess.run([fast_cdp] + sys.argv[2:])
            sys.exit(res.returncode)

    prog_name = Path(sys.argv[0]).name
    if prog_name not in ("local-hub", "skills-hub"):
        prog_name = "local-hub"

    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Local Hub — Unified Local Hardware Inference & Skills Gateway for Workstation"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # 1. Native Local LLM (:8080 Genesis 35B)
    p_llm = sub.add_parser("llm", help="Query local Dual-GPU Qwen3.6-35B Genesis on :8080")
    p_llm.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to llm_client")

    # 2. Native Local OCR (:8085 LightOnOCR-3-1B)
    p_ocr = sub.add_parser("ocr", help="Local vision OCR for slides, PDFs, and images on :8085")
    p_ocr.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to ocr engine")

    # 3. Native Local Decision (:8083 OneJev1.5-4B / :8090 JPT-4B)
    p_decide = sub.add_parser("decide", help="Premier calibrated decisions via OneJev1.5-4B on :8083")
    p_decide.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to decide engine")

    # Also alias 'jev' to 'decide'
    p_jev = sub.add_parser("jev", help="Alias for decide")
    p_jev.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to decide engine")

    # 4. Native Local ASR (:8081 Nemotron)
    p_asr = sub.add_parser("asr", help="Local speech-to-text via audio.cpp Nemotron on :8081")
    p_asr.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to asr engine")

    # 5. Native Fast-CDP Browser Automation (:9222)
    p_cdp = sub.add_parser("cdp", aliases=["browser"], help="Direct sub-second browser verification via fast-cdp on :9222")
    p_cdp.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to fast-cdp")

    # 6. Status / Health Check
    sub.add_parser("status", help="Live health check of all local inference endpoints (:8080–:8090)")
    sub.add_parser("health", help="Alias for status")
    p_mesh = sub.add_parser("mesh", help="View status and Tailscale routing endpoints")
    p_mesh.add_argument("--json", action="store_true", help="Output as JSON")

    # 6. Skill Discovery & Uber Protocol
    p_search = sub.add_parser("search", help="Search skills by intent across full body content")
    p_search.add_argument("query", help="Intent query")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")
    p_search.add_argument("--all", action="store_true", help="Search across both active and sidelined/archived skills")

    p_list = sub.add_parser("list", help="List all registered skills in the vault")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")
    p_list.add_argument("--all", action="store_true", help="Include sidelined (glitch-cat) and archived skills")

    p_tools = sub.add_parser("tools", help="List executable scripts/tools inside a skill")
    p_tools.add_argument("skill", help="Name of skill")

    p_inspect = sub.add_parser("inspect", help="Inspect exact usage contract and schema for 1 skill")
    p_inspect.add_argument("skill", help="Name of skill to inspect")

    p_run = sub.add_parser("run", help="Execute any skill with Response Projection & Disk Buffering")
    p_run.add_argument("skill", help="Name of skill to run")
    p_run.add_argument("--out", default=None, help="Buffer raw execution output to disk file")
    p_run.add_argument("--project", default=None, help="Comma-separated fields to project from JSON output")
    p_run.add_argument("--jq", default=None, help="JQ filter expression to project output")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the skill")

    args = parser.parse_args()

    if args.action == "llm":
        exec_internal_script("llm_client.py", args.args)
    elif args.action == "ocr":
        exec_internal_script("ocr.py", args.args)
    elif args.action in ("decide", "jev"):
        exec_internal_script("decide.py", args.args)
    elif args.action == "asr":
        exec_internal_script("asr.py", args.args)
    elif args.action in ("cdp", "browser"):
        fast_cdp = shutil.which("fast-cdp") or "/run/media/rodri/AI/skills/hybrid-browser/scripts/fast-cdp"
        res = subprocess.run([fast_cdp] + args.args)
        sys.exit(res.returncode)
    elif args.action in ("status", "health"):
        cmd_status(as_json=False)
    elif args.action == "mesh":
        cmd_status(as_json=args.json)
    elif args.action == "search":
        cmd_search(args.query, as_json=args.json, search_all=args.all)
    elif args.action == "list":
        cmd_list(as_json=args.json, show_all=args.all)
    elif args.action == "tools":
        cmd_tools(args.skill)
    elif args.action == "inspect":
        cmd_inspect(args.skill)
    elif args.action == "run":
        cmd_run(args.skill, args.args, out_path=args.out, project_fields=args.project, jq_expr=args.jq)


if __name__ == "__main__":
    main()
