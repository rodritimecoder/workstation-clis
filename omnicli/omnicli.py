#!/usr/bin/env python3
"""
omnicli — the Uber OmniCLI: one late-binding gateway to every local tool.

Two faces over one catalog:

  Face A (CLI / Code Mode)   omnicli search | describe | invoke | status
  Face B (MCP stdio server)  omnicli mcp   →  4 meta-tools over JSON-RPC

The catalog is a BM25 (SQLite FTS5) index over the full body of every skill,
with hand-curated aliases in a separately weighted column. An agent discovers
a tool by *intent*, then pulls exactly one tool's contract, then invokes it
with a bounded response. Nothing else ever enters the context window.

Native local inference (llm / ocr / decide / asr) is available as first-class
tools, and as a direct subcommand for interactive use.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
if SCRIPT_PATH.parent.name == "scripts":
    SKILL_DIR = SCRIPT_PATH.parent.parent
else:
    SKILL_DIR = SCRIPT_PATH.parent

SCRIPTS_DIR = SKILL_DIR / "scripts"
VENV_PYTHON = SKILL_DIR / ".venv" / "bin" / "python"

sys.path.insert(0, str(SKILL_DIR))

try:
    from catalog import builder, registry, search  # noqa: E402
except ImportError:  # pragma: no cover - degraded install
    builder = registry = search = None  # type: ignore

# The response cap. An agent must never be able to pull an unbounded payload
# into its context window, even by forgetting the flags.
DEFAULT_MAX_BYTES = 8000
PREVIEW_HEAD = 3000
PREVIEW_TAIL = 1500


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------

def get_python_for_script() -> str:
    if VENV_PYTHON.is_file() and os.access(VENV_PYTHON, os.X_OK):
        return str(VENV_PYTHON)
    return sys.executable


def exec_internal_script(script_name: str, args: list[str]) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.is_file():
        sys.exit(f"❌ Error: Internal engine script not found at {script_path}")
    cmd = [get_python_for_script(), str(script_path)] + args
    sys.exit(subprocess.run(cmd).returncode)


def _require_catalog():
    if builder is None:
        sys.exit("❌ Error: omnicli catalog package not importable from %s" % SKILL_DIR)
    con = builder.connect()
    builder.ensure_built(con, progress=False)
    return con


# --------------------------------------------------------------------------
# invoke argument parsing
# --------------------------------------------------------------------------
#
# `invoke` is parsed manually rather than by argparse. Two reasons:
#
# 1. argparse.REMAINDER swallows every token after the first positional, so
#    `omnicli invoke <tool> --out FILE` would silently lose --out.
# 2. Tool flags and gateway flags collide. --out, --project and --json are
#    all real flags on real tools in this collection. The gateway's own
#    flags are therefore prefixed `--omni-`, and anything else after the
#    tool id is passed to the tool untouched. "--" also forces the split.

INVOKE_VALUE_FLAGS = {
    "--omni-buffer": "buffer",
    "--omni-project": "project",
    "--omni-jq": "jq",
    "--omni-grep": "grep",
    "--omni-max-bytes": "max_bytes",
    "--omni-timeout": "timeout",
}
INVOKE_BOOL_FLAGS = {"--omni-json": "json"}


def parse_invoke_args(argv: list[str]) -> tuple[str | None, dict, list[str]]:
    """Split `invoke` arguments into (tool_id, gateway options, tool args)."""
    opts: dict[str, Any] = {
        "buffer": None, "project": None, "jq": None, "grep": None,
        "max_bytes": DEFAULT_MAX_BYTES, "json": False, "timeout": 300.0,
    }
    tool_args: list[str] = []
    tool_id: str | None = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            tool_args.extend(argv[i + 1:])
            break
        if a in INVOKE_VALUE_FLAGS:
            key = INVOKE_VALUE_FLAGS[a]
            if i + 1 < len(argv):
                val = argv[i + 1]
                opts[key] = int(val) if key in ("max_bytes", "timeout") else val
                i += 2
            else:
                i += 1
            continue
        if a in INVOKE_BOOL_FLAGS:
            opts[INVOKE_BOOL_FLAGS[a]] = True
            i += 1
            continue
        if a.startswith("--omni-"):
            i += 1
            continue
        if tool_id is None and not a.startswith("-"):
            tool_id = a
            i += 1
            continue
        tool_args.append(a)
        i += 1
    return tool_id, opts, tool_args


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

def _tailscale_address() -> str | None:
    try:
        p = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=6)
        if p.returncode == 0:
            data = json.loads(p.stdout)
            ips = data.get("Self", {}).get("TailscaleIPs", [])
            if ips:
                return ips[0]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _service_online(port: int, ts_addr: str | None) -> bool:
    """A service counts as online if loopback *or* the tailnet answers.

    Several daemons on this box bind only the Tailscale interface, so a
    loopback-only probe reports them as dead while they are serving.
    """
    if _port_open(port):
        return True
    if ts_addr and _port_open(port, ts_addr):
        return True
    return False


SERVICES = [
    {"port": 4000, "name": "LiteLLM Dynamic Gateway", "role": "Multi-model proxy & failover"},
    {"port": 8000, "name": "llama-swap Controller", "role": "Model hot-swapper"},
    {"port": 8080, "name": "Genesis 35B Primary LLM", "role": "Dual-GPU flagship coder"},
    {"port": 8081, "name": "audio.cpp ASR & TTS", "role": "Streaming speech-to-text / TTS"},
    {"port": 8083, "name": "vllm-d3-mini Decision Gating", "role": "Premier calibrated decisions"},
    {"port": 8084, "name": "CrispEmbed Scene-Text OCR", "role": "Ultra-fast text detection"},
    {"port": 8085, "name": "LightOnOCR Flagship OCR", "role": "Document and slide OCR"},
    {"port": 8087, "name": "Embedding Server (BGE / EmbeddingGemma)", "role": "Optional re-ranker for catalog search"},
    {"port": 8089, "name": "OneJev1.5-4B Decision Fallback", "role": "Calibrated decision fallback"},
    {"port": 8090, "name": "JPT-4B Decision Engine", "role": "System One gating with vision"},
    {"port": 9222, "name": "Chromium CDP DevTools", "role": "Direct WebSocket/CDP browser control"},
]


def cmd_status(as_json: bool = False):
    ts_addr = _tailscale_address()
    results = []
    for s in SERVICES:
        online = _service_online(s["port"], ts_addr)
        results.append({
            "service": s["name"],
            "port": s["port"],
            "status": "ONLINE" if online else "OFFLINE",
            "local_url": f"http://127.0.0.1:{s['port']}",
            "tailnet_url": f"http://{ts_addr}:{s['port']}" if ts_addr else "",
            "role": s["role"],
        })

    catalog_info = {}
    tier = "unavailable"
    if builder is not None:
        try:
            con = builder.connect()
            built = builder.ensure_built(con, progress=False)
            tier = "bm25+rerank" if search.embedding_available() else "bm25"
            catalog_info = {
                "skills": built.get("skills"),
                "tools": built.get("tools"),
                "docs": built.get("docs"),
                "built_at": built.get("built_at"),
                "rebuilt": built.get("rebuilt"),
                "db": str(builder.db_path()),
            }
        except Exception as exc:  # pragma: no cover
            catalog_info = {"error": str(exc)}

    payload = {
        "tailscale_address": ts_addr,
        "services": results,
        "catalog": catalog_info,
        "retrieval_tier": tier,
    }

    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print("\n🌐 [omnicli — Workstation Inference & Tailnet]")
    print(f"   Tailnet address: {ts_addr or 'offline'}")
    print()
    print("   " + f"{'SERVICE':<42} │ {'STATUS':<10} │ ENDPOINT")
    print("   " + "─" * 43 + "┼" + "─" * 12 + "┼" + "─" * 26)
    for r in results:
        icon = "🟢 ONLINE " if r["status"] == "ONLINE" else "⚪ OFFLINE"
        ep = r["local_url"] if r["status"] == "ONLINE" else ""
        print(f"   {r['service']:<42} │ {icon:<10} │ {ep}")

    print()
    if catalog_info.get("skills") is not None:
        print(f"   📇 Catalog : {catalog_info['skills']} skills · {catalog_info['tools']} tools · "
              f"{catalog_info['docs']} docs")
        print(f"   🔎 Retrieval tier: {tier}")
        print(f"   💾 Index   : {catalog_info.get('db')}")
    print("   💡 Tip: `tailscale-ops serve-mesh` exposes all services over private HTTPS.")
    print()


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------

def cmd_search(query: str, as_json: bool = False, limit: int = 6,
               explain: bool = False, no_rerank: bool = False):
    con = _require_catalog()
    res = search.search(con, query, limit=limit, rerank_enabled=not no_rerank, explain=explain)

    if as_json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if not res["results"]:
        print(f"\n🔍 No match for: {query!r}")
        if res.get("note"):
            print(f"   {res['note']}")
        print("   Try a different phrasing, or `omnicli list` to browse the registry.\n")
        return

    print(f"\n🔍 [omnicli] intent: {query!r}   tier={res['tier']}   "
          f"candidates={res['candidate_chunks']}\n")
    for i, r in enumerate(res["results"], 1):
        print(f"  {i}. {r['skill']}   score={r['score']:.2f}  "
              f"lex={r['lexical_score']:.2f}  coord={r['coordination']:.2f}  "
              f"chunks={r['coverage']}")
        if explain:
            print(f"       matched : {', '.join(r.get('matched_terms', []))}")
            print(f"       top hit : [{r['chunks'][0]['kind']}] {r['chunks'][0]['title']}")
            print(f"       {r['chunks'][0]['snippet'][:180]}")
        else:
            print(f"       {r['chunks'][0]['snippet'][:150]}")
        print(f"       → omnicli tools {r['skill']}")
        print()
    print("   Next: `omnicli describe <tool_id>` for one contract, "
          "`omnicli invoke <tool_id> --args ...` to run it.\n")


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def cmd_list(as_json: bool = False, show_all: bool = False):
    con = _require_catalog()
    rows = con.execute(
        "SELECT name, dir_name, description, status, cli, tools FROM skills ORDER BY name"
    ).fetchall()
    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
        return
    print(f"\n📦 [omnicli registry] {len(rows)} skills\n")
    for r in rows:
        tag = "" if r["status"] == "active" else f" [{r['status'].upper()}]"
        cli = "  cli:" + Path(r["cli"]).name if r["cli"] else ""
        print(f"  • {r['name']:<28}{tag} {r['tools']:>3} tools{cli}")
        if r["description"]:
            print(f"    {r['description'][:120]}")
    print()


def cmd_tools(skill_name: str, as_json: bool = False):
    con = _require_catalog()
    rows = con.execute(
        "SELECT id, kind, summary FROM tools WHERE skill = ? OR skill = ? ORDER BY id",
        (skill_name, skill_name),
    ).fetchall()
    if not rows:
        matches = con.execute(
            "SELECT DISTINCT skill FROM tools WHERE skill LIKE ?", (f"%{skill_name}%",)
        ).fetchall()
        if matches:
            print(f"❌ No skill named {skill_name!r}. Did you mean: "
                  f"{', '.join(m['skill'] for m in matches)}?")
            sys.exit(1)
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")

    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
        return
    print(f"\n🛠️  [omnicli tools] {skill_name}  ({len(rows)} tools)\n")
    for r in rows:
        print(f"   - {r['id']}   [{r['kind']}]")
        if r["summary"]:
            print(f"       {r['summary'][:150]}")
    print(f"\n   Contract:  omnicli describe <tool_id>")
    print(f"   Execute :  omnicli invoke <tool_id> [args...]\n")


def cmd_describe(tool_id: str, as_json: bool = False):
    """Return the exact input contract for ONE tool."""
    con = _require_catalog()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        # Allow a bare skill name: describe the skill's primary script.
        cands = con.execute(
            "SELECT id FROM tools WHERE skill = ? AND kind = 'script' LIMIT 1", (tool_id,)
        ).fetchall()
        if not cands:
            sys.exit(f"❌ Error: no tool named {tool_id!r}. "
                     f"Use `omnicli tools <skill>` to list a skill's tools.")
        row = con.execute("SELECT * FROM tools WHERE id = ?", (cands[0]["id"],)).fetchone()

    contract = json.loads(row["contract"] or "{}")
    skill = con.execute("SELECT * FROM skills WHERE name = ?", (row["skill"],)).fetchone()

    payload = {
        "id": row["id"],
        "skill": row["skill"],
        "kind": row["kind"],
        "summary": row["summary"],
        "path": row["path"],
        "argv": json.loads(row["argv"] or "[]"),
        "aliases": json.loads(skill["aliases"] or "[]") if skill else [],
        "contract": contract,
    }

    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"\n📄 [omnicli describe] {row['id']}\n")
    print(f"   skill   : {row['skill']}")
    print(f"   kind    : {row['kind']}")
    if row["summary"]:
        print(f"   summary : {row['summary']}")
    if skill and skill["description"]:
        print(f"   about   : {skill['description'][:200]}")
    if payload["aliases"]:
        print(f"   aliases : {', '.join(payload['aliases'])}")

    if contract.get("usage"):
        print(f"\n   {contract['usage']}")
    if contract.get("flags"):
        print(f"\n   flags      : {' '.join(contract['flags'])}")
    if contract.get("positionals"):
        print(f"   positionals: {' '.join(contract['positionals'])}")
    if contract.get("subcommands"):
        print("\n   subcommands:")
        for sub in contract["subcommands"]:
            alias = f" ({', '.join(sub['aliases'])})" if sub.get("aliases") else ""
            desc = f" — {sub['summary']}" if sub.get("summary") else ""
            print(f"      {sub['name']}{alias}{desc}")
    if contract.get("help"):
        print("\n" + "\n".join("   | " + ln for ln in contract["help"].splitlines()[:40]))
    print(f"\n   Run: omnicli invoke {row['id']} [args...]\n")


# --------------------------------------------------------------------------
# invoke
# --------------------------------------------------------------------------

def _project(raw: str, fields: list[str] | None, jq_expr: str | None) -> str:
    if jq_expr and shutil.which("jq"):
        try:
            p = subprocess.run(["jq", jq_expr], input=raw, text=True, capture_output=True)
            if p.returncode == 0:
                return p.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    if fields:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return json.dumps({k: v for k, v in data.items() if k in fields}, indent=2)
            if isinstance(data, list):
                return json.dumps(
                    [{k: v for k, v in it.items() if k in fields} if isinstance(it, dict) else it
                     for it in data], indent=2)
        except (ValueError, TypeError):
            pass
    return raw


def _cap(raw: str, max_bytes: int) -> tuple[str, bool, int]:
    """Bound the payload. Returns (text, truncated, original_size).

    The preview is scaled to fit *within* the cap, including the banner
    itself — a cap smaller than the preview must still produce a result no
    larger than the cap, or the guarantee is meaningless.
    """
    data = raw.encode("utf-8", errors="replace")
    total = len(data)
    if total <= max_bytes:
        return raw, False, total

    # Reserve a conservative banner allowance first; the exact banner is
    # built after the split is known, and the final clamp guarantees the cap.
    budget = max(max_bytes - 300, 0)
    if budget <= 0:
        tiny = f"… [omnicli] output elided (cap {max_bytes})."
        return tiny.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore"), True, total

    head_len = int(budget * 0.66)
    tail_len = budget - head_len
    head = data[:head_len].decode("utf-8", errors="ignore")
    tail = data[-tail_len:].decode("utf-8", errors="ignore") if tail_len else ""
    omitted = total - head_len - tail_len

    banner = (
        f"… [omnicli] {omitted} bytes elided ({total} total, cap {max_bytes}). "
        f"Re-run with --omni-buffer FILE to capture the full payload, "
        f"or --omni-max-bytes {total} to lift the cap."
    )
    if max_bytes < len(banner) + 40:
        banner = f"… [omnicli] {omitted} bytes elided (cap {max_bytes})."
    text = f"{head}\n\n{banner}\n\n{tail}"
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        text = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return text, True, total


def cmd_invoke(tool_id: str, extra_args: list[str], out_path: str | None = None,
               project_fields: str | None = None, jq_expr: str | None = None,
               grep: str | None = None, max_bytes: int = DEFAULT_MAX_BYTES,
               as_json: bool = False, timeout: float = 300.0):
    con = _require_catalog()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        sys.exit(f"❌ Error: no tool named {tool_id!r}. "
                 f"Use `omnicli tools <skill>` to list a skill's tools.")

    argv = json.loads(row["argv"] or "[]")
    cmd = [str(a).replace("{python}", sys.executable).replace("{skill}", str(SKILL_DIR)) for a in argv]
    cmd += list(extra_args)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        code = proc.returncode
    except subprocess.TimeoutExpired:
        raw = f"⏱️ omnicli: tool timed out after {timeout}s"
        code = 124
    except OSError as exc:
        raw = f"❌ omnicli: failed to execute: {exc}"
        code = 127

    fields = [f.strip() for f in project_fields.split(",")] if project_fields else None
    projected = _project(raw, fields, jq_expr)

    if grep:
        try:
            import re as _re
            pattern = _re.compile(grep)
            projected = "\n".join(ln for ln in projected.splitlines() if pattern.search(ln))
        except _re.error as exc:
            sys.exit(f"❌ Error: invalid --grep pattern: {exc}")

    capped, truncated, original = _cap(projected, max_bytes)

    if out_path:
        p = Path(out_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(projected, encoding="utf-8")
        print(f"💾 Full output buffered to: {p}  ({original} bytes)")
        if truncated:
            print(f"📊 Preview below (cap {max_bytes} bytes).")
        else:
            print(f"📊 Payload fit within the cap ({original} bytes).")
        print()
        print(capped)
        sys.exit(code)

    if as_json:
        print(json.dumps({
            "tool": tool_id, "exit_code": code, "bytes": original,
            "truncated": truncated, "output": capped,
        }, indent=2, ensure_ascii=False))
        sys.exit(code)

    print(capped)
    sys.exit(code)


# --------------------------------------------------------------------------
# index / eval
# --------------------------------------------------------------------------

def cmd_index(rebuild: bool = False, with_contracts: bool = True, as_json: bool = False):
    con = builder.connect()
    summary = builder.ensure_built(con, rebuild=rebuild, with_contracts=with_contracts, progress=True)
    if as_json:
        print(json.dumps(summary, indent=2))
        return
    verb = "rebuilt" if summary.get("rebuilt") else "up to date"
    print(f"\n📇 Catalog {verb}: {summary['skills']} skills · {summary['tools']} tools · "
          f"{summary['docs']} docs")
    print(f"   {builder.db_path()}\n")


def cmd_eval(verbose: bool = False, as_json: bool = False):
    runner = SKILL_DIR / "tests" / "eval_runner.py"
    if not runner.is_file():
        sys.exit("❌ Error: tests/eval_runner.py not found next to omnicli.")
    args = [sys.executable, str(runner)]
    if verbose:
        args.append("--verbose")
    if as_json:
        args.append("--json")
    sys.exit(subprocess.run(args).returncode)


# --------------------------------------------------------------------------
# mcp
# --------------------------------------------------------------------------

def cmd_mcp(as_json: bool = False):
    server = SKILL_DIR / "mcp" / "server.py"
    if not server.is_file():
        sys.exit("❌ Error: mcp/server.py not found next to omnicli.")
    sys.exit(subprocess.run([sys.executable, str(server)]).returncode)


# --------------------------------------------------------------------------
# compat
# --------------------------------------------------------------------------

def cmd_inspect(skill_name: str):
    """Legacy: dump a skill's SKILL.md body."""
    skills = registry.load_all_skills(include_sidelined=True)
    target = None
    for name, s in skills.items():
        if name == skill_name or s["dir_name"] == skill_name:
            target = s
            break
    if not target:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")
    status_tag = f" [{target.get('status').upper()}]" if target.get("status") != "active" else ""
    print(f"\n📖 [omnicli inspect] {target['name']}{status_tag}\n")
    print(f"   Path: {target['path']}")
    print(f"   Tools: omnicli tools {target['name']}\n")
    import re
    content = Path(target["md_path"]).read_text(encoding="utf-8")
    print(re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL))


def cmd_run(skill_name: str, extra_args: list[str], out_path: str | None = None,
            project_fields: str | None = None, jq_expr: str | None = None):
    """Legacy: run a skill by name, with projection and disk buffering."""
    if skill_name in ("llm", "llm-cli"):
        exec_internal_script("llm_client.py", extra_args)
    elif skill_name in ("ocr", "ocr-cli"):
        exec_internal_script("ocr.py", extra_args)
    elif skill_name in ("decide", "jev", "jev-cli"):
        exec_internal_script("decide.py", extra_args)
    elif skill_name in ("asr", "audiocpp-asr"):
        exec_internal_script("asr.py", extra_args)

    con = _require_catalog()
    row = con.execute(
        "SELECT id FROM tools WHERE skill = ? AND kind = 'script' ORDER BY id LIMIT 1",
        (skill_name,),
    ).fetchone()
    if row is None:
        row = con.execute(
            "SELECT id FROM tools WHERE id = ?", (f"{skill_name}/cli",)
        ).fetchone()
    if row is None:
        sys.exit(f"❌ Error: Skill '{skill_name}' not found.")
    cmd_invoke(row["id"], extra_args, out_path=out_path,
               project_fields=project_fields, jq_expr=jq_expr)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        subcmd = sys.argv[1]
        if subcmd == "invoke":
            # Parsed manually: see parse_invoke_args.
            tool_id, opts, tool_args = parse_invoke_args(sys.argv[2:])
            if not tool_id:
                sys.exit("❌ Error: `omnicli invoke` needs a tool id. "
                         "Use `omnicli tools <skill>` to list them.")
            cmd_invoke(
                tool_id, tool_args,
                out_path=opts["buffer"], project_fields=opts["project"],
                jq_expr=opts["jq"], grep=opts["grep"],
                max_bytes=opts["max_bytes"], as_json=opts["json"],
                timeout=float(opts["timeout"]),
            )
        if subcmd == "llm":
            exec_internal_script("llm_client.py", sys.argv[2:])
        elif subcmd == "ocr":
            exec_internal_script("ocr.py", sys.argv[2:])
        elif subcmd in ("decide", "jev"):
            exec_internal_script("decide.py", sys.argv[2:])
        elif subcmd == "asr":
            exec_internal_script("asr.py", sys.argv[2:])
        elif subcmd in ("cdp", "browser"):
            fast_cdp = shutil.which("fast-cdp") or str(
                registry.resolve_skills_dir() / "hybrid-browser" / "scripts" / "fast-cdp")
            sys.exit(subprocess.run([fast_cdp] + sys.argv[2:]).returncode)

    prog_name = Path(sys.argv[0]).name
    if prog_name not in ("omnicli", "uber", "local-hub", "skills-hub"):
        prog_name = "omnicli"

    if prog_name in ("local-hub", "skills-hub"):
        print("⚠️  'local-hub'/'skills-hub' are deprecated aliases for 'omnicli'. "
              "Use `omnicli` directly.", file=sys.stderr)

    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="omnicli — unified late-binding gateway to every local tool",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # --- native local inference -------------------------------------
    p = sub.add_parser("llm", help="Query the local dual-GPU Genesis 35B on :8080")
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("ocr", help="Local document/slide/image OCR on :8085")
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("decide", help="Calibrated decisions (bool/choice/score) on :8083")
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("jev", help="Alias for decide")
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("asr", help="Local speech-to-text via audio.cpp on :8081")
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("cdp", aliases=["browser"], help="Fast CDP browser control on :9222")
    p.add_argument("args", nargs=argparse.REMAINDER)

    # --- catalog -----------------------------------------------------
    p = sub.add_parser("search", help="Find tools by intent (BM25 over every skill body)")
    p.add_argument("query", help="Natural-language intent")
    p.add_argument("--json", action="store_true")
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--explain", action="store_true", help="Show matched terms and the winning chunk")
    p.add_argument("--no-rerank", action="store_true", help="Skip the optional embedding re-ranker")

    p = sub.add_parser("list", help="List every skill in the registry")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="Include sidelined and archived skills")

    p = sub.add_parser("tools", help="List the tools belonging to a skill")
    p.add_argument("skill")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("describe", help="Show the exact input contract for ONE tool")
    p.add_argument("tool_id")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("invoke", help="Execute a tool with bounded output",
                       add_help=False)
    p.add_argument("tool_id")
    p.add_argument("--omni-buffer", default=None, help="Buffer the full output to a file")
    p.add_argument("--omni-project", default=None, help="Comma-separated fields to keep from JSON output")
    p.add_argument("--omni-jq", default=None, help="JQ filter expression")
    p.add_argument("--omni-grep", default=None, help="Keep only lines matching this regex")
    p.add_argument("--omni-max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                   help=f"Hard cap on returned bytes (default {DEFAULT_MAX_BYTES})")
    p.add_argument("--omni-json", action="store_true")
    p.add_argument("--omni-timeout", type=float, default=300.0)
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("index", help="Build or refresh the catalog index")
    p.add_argument("--rebuild", action="store_true", help="Force a full rebuild")
    p.add_argument("--no-contracts", action="store_true", help="Skip --help contract extraction")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("eval", help="Run the golden routing evaluation")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true")

    sub.add_parser("mcp", help="Run the MCP stdio server (4 meta-tools)")

    p = sub.add_parser("status", help="Health of every local service, the catalog, and the retrieval tier")
    p.add_argument("--json", action="store_true")

    sub.add_parser("health", help="Alias for status")

    # --- compat ------------------------------------------------------
    p = sub.add_parser("inspect", help="(legacy) Print a skill's SKILL.md body")
    p.add_argument("skill")

    p = sub.add_parser("run", help="(legacy) Run a skill by name")
    p.add_argument("skill")
    p.add_argument("--out", default=None)
    p.add_argument("--project", default=None)
    p.add_argument("--jq", default=None)
    p.add_argument("args", nargs=argparse.REMAINDER)

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
        fast_cdp = shutil.which("fast-cdp") or str(
            registry.resolve_skills_dir() / "hybrid-browser" / "scripts" / "fast-cdp")
        sys.exit(subprocess.run([fast_cdp] + args.args).returncode)
    elif args.action == "search":
        cmd_search(args.query, as_json=args.json, limit=args.limit,
                   explain=args.explain, no_rerank=args.no_rerank)
    elif args.action == "list":
        cmd_list(as_json=args.json, show_all=args.all)
    elif args.action == "tools":
        cmd_tools(args.skill, as_json=args.json)
    elif args.action == "describe":
        cmd_describe(args.tool_id, as_json=args.json)
    elif args.action == "index":
        cmd_index(rebuild=args.rebuild, with_contracts=not args.no_contracts, as_json=args.json)
    elif args.action == "eval":
        cmd_eval(verbose=args.verbose, as_json=args.json)
    elif args.action == "mcp":
        cmd_mcp()
    elif args.action in ("status", "health"):
        cmd_status(as_json=args.json)
    elif args.action == "inspect":
        cmd_inspect(args.skill)
    elif args.action == "run":
        cmd_run(args.skill, args.args, out_path=args.out,
                project_fields=args.project, jq_expr=args.jq)


if __name__ == "__main__":
    main()
