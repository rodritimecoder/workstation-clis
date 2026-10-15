#!/usr/bin/env python3
"""
skills_hub.py — Meta-Tool Discovery and Execution Gateway for AI Agent Skills
Implements the Uber OmniMCP / aifx "Code Mode" Protocol:
  1. Full-Body Search across SKILL.md and scripts (91.7% routing signal)
  2. 4-Step Funnel: discover -> tools -> schema -> invoke
  3. Response Projection (--project, --jq) & Disk Buffering (--out) to eliminate context bloat
"""

import argparse
import json
import os
import re
import shutil
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

            # Enumerate internal executable scripts
            scripts_dir = item / "scripts"
            scripts = []
            if scripts_dir.is_dir():
                for sf in scripts_dir.iterdir():
                    if sf.is_file() and (sf.suffix in (".py", ".sh") or os.access(sf, os.X_OK)):
                        scripts.append(sf.name)

            skills[name] = {
                "name": name,
                "dir_name": item.name,
                "path": str(item),
                "description": desc,
                "md_path": str(skill_md),
                "full_text": content,
                "scripts": scripts,
            }
    return skills


def cmd_list(as_json=False):
    skills = load_all_skills()
    if as_json:
        data = [
            {"name": s["name"], "dir": s["dir_name"], "description": s["description"], "scripts": s["scripts"]}
            for s in skills.values()
        ]
        print(json.dumps(data, indent=2))
        return

    print(f"\n📦 [Skills Hub / Uber Protocol] Registered Skills ({len(skills)} in vault):")
    print(f"{'Skill Name':<28} │ {'Description'}")
    print("─" * 29 + "┼" + "─" * 50)
    for s in skills.values():
        clean_desc = s["description"][:65] + "..." if len(s["description"]) > 65 else s["description"]
        print(f"{s['name']:<28} │ {clean_desc}")


def cmd_search(query: str, as_json=False):
    """Full-body search matching titles, descriptions, headers, and code examples."""
    skills = load_all_skills()
    q_tokens = [t.lower() for t in query.split() if len(t) > 1]
    scored = []

    for s in skills.values():
        score = 0
        name_lower = s["name"].lower()
        desc_lower = s["description"].lower()
        text_lower = s["full_text"].lower()

        for t in q_tokens:
            if t == name_lower:
                score += 15
            elif t in name_lower:
                score += 8
            if t in desc_lower:
                score += 5
            # Header or command matches get extra signal
            if f"# {t}" in text_lower or f"## {t}" in text_lower:
                score += 4
            elif t in text_lower:
                score += 1

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    if as_json:
        results = [
            {"name": s["name"], "score": score, "description": s["description"], "path": s["path"], "scripts": s["scripts"]}
            for score, s in scored[:5]
        ]
        print(json.dumps(results, indent=2))
        return

    print(f"\n🔍 [Uber Protocol Search] Intent: '{query}'")
    if not scored:
        print("  (No matching skills found in vault)")
        return

    for score, s in scored[:5]:
        print(f"\n  • 🎯 {s['name']} (relevance: {score})")
        print(f"    {s['description']}")
        if s["scripts"]:
            print(f"    Tools/Scripts: {', '.join(s['scripts'])}")
        print(f"    Inspect: skills-hub inspect {s['name']}")


def cmd_tools(skill_name: str):
    """Step 2: Narrow into runnable tools/scripts within the winning skill."""
    skills = load_all_skills()
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    print(f"\n🔧 [Uber Tools] Executable scripts for skill: {target['name']}")
    if not target["scripts"]:
        print("  (No standalone scripts found in scripts/; skill may be documentation-only or invoked via CLI)")
    else:
        for sc in target["scripts"]:
            print(f"  • {sc}")
            print(f"    Run via: skills-hub run {target['name']} {sc} --help")


def cmd_inspect(skill_name: str):
    """Step 3: Output the exact usage schema / rubric for this 1 tool only."""
    skills = load_all_skills()
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break

    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    print(f"\n📖 [Uber Schema & Contract] {target['name']}\n")
    content = Path(target["md_path"]).read_text(encoding="utf-8")
    clean_content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
    print(clean_content)


def apply_response_projection(raw_output: str, project_fields: list = None, jq_expr: str = None) -> str:
    """Pre-flight response projection: strips non-requested fields before LLM context."""
    if not raw_output.strip():
        return raw_output

    # 1. JQ expression if available
    if jq_expr and shutil.which("jq"):
        try:
            p = subprocess.run(["jq", jq_expr], input=raw_output, text=True, capture_output=True)
            if p.returncode == 0:
                return p.stdout.strip()
        except Exception:
            pass

    # 2. JSON field projection
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
    """Step 4: Execute tool with Response Projection & Disk Buffering."""
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
        # Match script name if explicitly requested in extra_args[0]
        if extra_args and extra_args[0] in [c.name for c in candidates]:
            primary = [c for c in candidates if c.name == extra_args[0]][0]
            extra_args = extra_args[1:]
        else:
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

    sys.stderr.write(f"🚀 [Uber Gateway] Executing: {' '.join(cmd)}\n")

    # If projection or disk buffering is requested, capture output
    if out_path or project_fields or jq_expr:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        raw_out = proc.stdout
        raw_err = proc.stderr

        if out_path:
            full_payload = raw_out + ("\n--- STDERR ---\n" + raw_err if raw_err else "")
            Path(out_path).write_text(full_payload, encoding="utf-8")
            sys.stderr.write(f"💾 [Disk Buffer] Wrote {len(full_payload.encode('utf-8'))} bytes to {out_path}\n")

        fields = [f.strip() for f in project_fields.split(",")] if project_fields else None
        projected = apply_response_projection(raw_out, fields, jq_expr)

        if out_path and not project_fields and not jq_expr:
            # Emit a lean receipt if buffered to disk without explicit projection
            print(f"[Execution Complete (exit {proc.returncode}). Full output saved to {out_path}]")
            if raw_err:
                print(f"Errors/Warnings:\n{raw_err.strip()[:1000]}")
        else:
            print(projected)

        sys.exit(proc.returncode)
    else:
        proc = subprocess.run(cmd)
        sys.exit(proc.returncode)


def cmd_mesh(as_json: bool = False):
    """Inspects status and reports local vs. Tailscale HTTPS routing endpoints for all workstation inference services."""
    services = [
        {"port": 4000, "name": "LiteLLM Dynamic Gateway", "env": "HOMELAB_LITELLM_URL"},
        {"port": 8000, "name": "llama-swap Controller", "env": "HOMELAB_LLAMASWAP_URL"},
        {"port": 8080, "name": "Genesis 35B Primary LLM", "env": "HOMELAB_GENESIS_URL"},
        {"port": 8081, "name": "audio.cpp Nemotron ASR & TTS", "env": "HOMELAB_AUDIOCPP_URL"},
        {"port": 8082, "name": "bge-small 384d Embeddings", "env": "HOMELAB_EMBEDDINGS_URL"},
        {"port": 8083, "name": "Imajev-4B Decision Gating", "env": "HOMELAB_IMAJEV_URL"},
        {"port": 8084, "name": "CrispEmbed Scene-Text OCR", "env": "HOMELAB_CRISPEMBED_URL"},
        {"port": 8085, "name": "LightOnOCR Flagship Document OCR", "env": "HOMELAB_LIGHTONOCR_URL"},
        {"port": 8088, "name": "DeskForge Visual GUI Grounding", "env": "HOMELAB_DESKFORGE_URL"},
        {"port": 8090, "name": "JPT-4B Decision Engine", "env": "HOMELAB_JPT_URL"},
        {"port": 3010, "name": "KasmVNC Browser Web Desktop", "env": "HOMELAB_KASMVNC_URL"},
    ]

    ts_dns = None
    ts_ip = None
    try:
        ts_out = subprocess.check_output(["tailscale", "status", "--json"], stderr=subprocess.DEVNULL)
        ts_data = json.loads(ts_out.decode("utf-8"))
        self_node = ts_data.get("Self", {})
        ts_dns = self_node.get("DNSName", "").rstrip(".")
        ts_ip = (self_node.get("TailscaleIPs") or [None])[0]
    except Exception:
        pass

    results = []
    import socket

    for s in services:
        port = s["port"]
        online = False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        try:
            sock.connect(("127.0.0.1", port))
            sock.close()
            online = True
        except Exception:
            pass

        local_url = f"http://127.0.0.1:{port}"
        ts_url = f"https://{ts_dns}:{port}" if ts_dns else f"http://{ts_ip}:{port}" if ts_ip else "Tailscale Offline"

        results.append({
            "service": s["name"],
            "port": port,
            "status": "ONLINE" if online else "OFFLINE",
            "local_url": local_url,
            "tailscale_url": ts_url,
            "env_var": s["env"],
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="skills-hub",
        description="Skills Hub — Uber OmniMCP & aifx Late-Binding Gateway for Agent Skills"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # 1. Discover / List
    p_list = sub.add_parser("list", help="List all registered skills in the vault")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    # 2. Search / Discover
    p_search = sub.add_parser("search", help="Step 1: Search skills by intent across full body content")
    p_search.add_argument("query", help="Intent query (e.g. 'speech transcription', 'canvas grades')")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")

    # 3. Tools
    p_tools = sub.add_parser("tools", help="Step 2: List executable scripts/tools inside a skill")
    p_tools.add_argument("skill", help="Name of skill")

    # 4. Inspect / Schema
    p_inspect = sub.add_parser("inspect", help="Step 3: Inspect exact usage contract and schema for 1 skill")
    p_inspect.add_argument("skill", help="Name of skill to inspect")

    # 5. Run / Invoke
    p_run = sub.add_parser("run", help="Step 4: Execute a skill with Response Projection & Disk Buffering")
    p_run.add_argument("skill", help="Name of skill to run")
    p_run.add_argument("--out", default=None, help="Buffer raw execution output to disk file")
    p_run.add_argument("--project", default=None, help="Comma-separated fields to project from JSON output")
    p_run.add_argument("--jq", default=None, help="JQ filter expression to project output")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the skill")

    # 6. Mesh (Tailscale & Local Inference Registry)
    p_mesh = sub.add_parser("mesh", help="View status and Tailscale routing endpoints for all local inference services")
    p_mesh.add_argument("--json", action="store_true", help="Output as JSON")

    # 7. Native Local LLM (:8080 Genesis 35B)
    p_llm = sub.add_parser("llm", help="Direct local LLM query to Qwen3.6-35B Genesis on :8080")
    p_llm.add_argument("prompt", help="Prompt or coding task")
    p_llm.add_argument("--stream", action="store_true", help="Stream response tokens in real-time")
    p_llm.add_argument("--fallback", action="store_true", help="Fallback to cloud if :8080 is offline")
    p_llm.add_argument("--out", help="Buffer output to disk file")

    # 8. Native Local ASR (:8081 Nemotron)
    p_asr = sub.add_parser("asr", help="Local speech-to-text via audio.cpp Nemotron on :8081")
    p_asr.add_argument("audio", help="Audio file path to transcribe")
    p_asr.add_argument("--engine", default="cli", choices=["cli", "server"], help="ASR engine mode (default: cli)")
    p_asr.add_argument("--out", help="Buffer transcript to file")

    # 9. Native Local Decision (:8083 Imajev-4B)
    p_decide = sub.add_parser("decide", help="Calibrated probability decisions via Imajev-4B on :8083")
    p_decide.add_argument("state", help="State or text to evaluate")
    p_decide.add_argument("question", help="The decision question")
    p_decide.add_argument("options", nargs="?", default=None, help="Options JSON, list, or omit for noul")

    # 10. Native Local OCR (:8085 LightOnOCR)
    p_ocr = sub.add_parser("ocr", help="Local vision OCR for slides, PDFs, and images on :8085")
    p_ocr.add_argument("file", help="PDF or image file to extract")
    p_ocr.add_argument("--pages", help="Page range (e.g. 1-3)")
    p_ocr.add_argument("--out", help="Buffer extracted text to file")

    # 11. Status / Health Check
    sub.add_parser("status", help="Live health check of all local hardware inference endpoints (:8080-:8090)")
    sub.add_parser("health", help="Alias for status")

    args = parser.parse_args()
    if args.action == "list":
        cmd_list(as_json=args.json)
    elif args.action == "search":
        cmd_search(args.query, as_json=args.json)
    elif args.action == "tools":
        cmd_tools(args.skill)
    elif args.action == "inspect":
        cmd_inspect(args.skill)
    elif args.action == "run":
        cmd_run(args.skill, args.args, out_path=args.out, project_fields=args.project, jq_expr=args.jq)
    elif args.action == "mesh":
        cmd_mesh(as_json=args.json)
    elif args.action == "llm":
        extra = []
        if args.stream:
            extra.append("--stream")
        if args.fallback:
            extra.append("--fallback")
        if args.out:
            extra.extend(["--out", args.out])
        extra.append(args.prompt)
        cmd_run("llm-cli", extra, out_path=args.out)
    elif args.action == "asr":
        cmd_run("audiocpp-asr", ["transcribe", args.audio, "--engine", args.engine], out_path=args.out)
    elif args.action == "decide":
        extra = [args.state, args.question]
        if args.options:
            extra.append(args.options)
        cmd_run("jev-cli", extra)
    elif args.action == "ocr":
        extra = [args.file]
        if args.pages:
            extra.extend(["--pages", args.pages])
        cmd_run("ocr-cli", extra, out_path=args.out)
    elif args.action in ("status", "health"):
        cmd_mesh(as_json=False)

