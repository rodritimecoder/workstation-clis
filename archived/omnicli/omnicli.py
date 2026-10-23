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
import re
import shutil
import subprocess
import sys
import time
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
    from catalog import aliases as aliases_mod
    from catalog import builder, health, invoke, policy, registry, search  # noqa: E402
except ImportError:  # pragma: no cover - degraded install
    aliases_mod = None
    builder = registry = search = health = invoke = policy = None  # type: ignore

# The response cap. An agent must never be able to pull an unbounded payload
# into its context window, even by forgetting the flags. The implementation
# lives in catalog.invoke so that the MCP face enforces the same ceiling.
DEFAULT_MAX_BYTES = invoke.DEFAULT_MAX_BYTES if invoke else 8000


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
            if i + 1 >= len(argv):
                sys.exit(f"❌ Error: {a} needs a value.")
            val = argv[i + 1]
            if key in ("max_bytes", "timeout"):
                try:
                    opts[key] = int(val) if key == "max_bytes" else float(val)
                except ValueError:
                    sys.exit(f"❌ Error: {a} expects a number, got {val!r}.")
            else:
                opts[key] = val
            i += 2
            continue
        if a in INVOKE_BOOL_FLAGS:
            opts[INVOKE_BOOL_FLAGS[a]] = True
            i += 1
            continue
        if a.startswith("--omni-"):
            # Silently dropping an unknown gateway flag is how a typo becomes
            # a silently unfiltered 8 KB payload. Say so and keep going: the
            # tool itself never sees `--omni-*`, so nothing else breaks.
            print(f"⚠️  omnicli: unknown gateway flag {a!r} ignored "
                  f"(known: {', '.join(sorted(INVOKE_VALUE_FLAGS | INVOKE_BOOL_FLAGS))})",
                  file=sys.stderr)
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

def cmd_status(as_json: bool = False):
    probe = health.probe_all()
    ts_addr = probe["tailscale_address"]
    results = probe["services"]

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
        icon = {"ONLINE": "🟢 ONLINE", "DEGRADED": "🟡 DEGRADED"}.get(r["status"], "⚪ OFFLINE")
        ep = r["local_url"] if r["status"] != "OFFLINE" else ""
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
               explain: bool = False, no_rerank: bool = False, rerank: str = "auto",
               chunks: bool = False):
    con = _require_catalog()
    mode = "never" if no_rerank else rerank
    res = search.search(con, query, limit=limit, rerank_enabled=mode, explain=explain)

    if as_json:
        # Routing needs names and scores; the chunk archive is opt-in. The
        # full shape is ~25 KB (~6.3k tokens) for ten results, which is more
        # context than the skill being routed to.
        if not chunks:
            res = dict(res)
            res["results"] = search.compact(res["results"])
            res["shape"] = "compact"
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
        top = r["chunks"][0]
        if top.get("kind") == "doc":
            rel = top["path"].split("/suites/")[-1]
            print(f"       → omnicli describe {r['skill']} --doc \"{rel}\"")
        else:
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
        "SELECT id, kind, summary, enabled FROM tools WHERE skill = ? ORDER BY id",
        (skill_name,),
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
        gate = "" if r["enabled"] else "   [disabled]"
        print(f"   - {r['id']}   [{r['kind']}]{gate}")
        if r["summary"]:
            print(f"       {r['summary'][:150]}")
    hidden = sum(1 for r in rows if not r["enabled"])
    print(f"\n   Contract:  omnicli describe <tool_id>")
    print(f"   Execute :  omnicli invoke <tool_id> [args...]")
    if hidden:
        print(f"   Gate    :  {hidden} tool(s) disabled; "
              f"`omnicli enable <tool_id>` after reviewing the contract\n")
    else:
        print()


def _describe_doc(con, name: str, query: str, as_json: bool = False):
    """Read one document the skill declared as part of its searchable body.

    The query is matched loosely: an exact title, a path suffix, a path
    fragment, or the file's stem. An agent that saw a snippet in a search
    result should be able to name the document the way the result named it.
    """
    q = query.strip().lower()
    rows = con.execute(
        "SELECT title, path, body, kind FROM docs WHERE skill = ? AND kind = 'doc'",
        (name,),
    ).fetchall()
    if not rows:
        sys.exit(f"❌ Error: {name!r} declares no documents. "
                 "Use `omnicli describe " + name + "` to see the skill itself.")

    scored = []
    for title, path, body, kind in rows:
        t = (title or "").lower()
        p = (path or "").lower()
        stem = Path(p).stem.lower()
        rel = "/".join(p.split("/suites/")[-1].split("/")) if "/suites/" in p else p
        score = 0
        if t == q or rel == q:
            score = 100
        elif t.startswith(q) or rel.startswith(q):
            score = 80
        elif t.endswith("/" + q) or rel.endswith("/" + q):
            score = 70
        elif q and q in t:
            score = 50
        elif q and q in p:
            score = 40
        elif stem == q:
            score = 30
        if score:
            scored.append((score, title, path, body))
    if not scored:
        sys.exit(f"❌ Error: no document matching {query!r} in {name!r}.")

    scored.sort(key=lambda r: -r[0])
    best = scored[0]
    _, title, path, body = best
    payload = {"skill": name, "title": title, "path": path,
               "tokens": len(body) // 4, "body": body}
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(f"\n📖 [{name}] document: {title}  (~{payload['tokens']} tokens)\n")
    print(body)
    print(f"\n   source: {path}")
    if len(scored) > 1:
        others = ", ".join(sorted({t for _, t, _, _ in scored[1:5]}))
        print(f"   also matched: {others}")


def _describe_skill(con, name: str, section_name: str, as_json: bool = False, doc_name: str = ""):
    """A skill id: frontmatter + outline, or one section on request."""
    from catalog import skilldoc

    row = con.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
    if row is None:
        sys.exit(f"❌ Error: no skill named {name!r}.")
    md_path = row["md_path"]
    if not md_path or not Path(md_path).is_file():
        sys.exit(f"❌ Error: skill {name!r} has no readable SKILL.md.")

    doc = skilldoc.load_skill_doc(md_path)
    tools = con.execute(
        "SELECT id, kind FROM tools WHERE skill = ? ORDER BY kind, id", (name,)
    ).fetchall()

    if doc_name:
        return _describe_doc(con, name, doc_name, as_json)

    if section_name:
        section = skilldoc.pick_section(doc, section_name)
        if section is None:
            sys.exit(f"❌ Error: no section {section_name!r} in {name!r}. Available: "
                     + ", ".join(s["heading"] for s in doc["sections"] if s["heading"]))
        if as_json:
            print(json.dumps({
                "skill": name, "section": section["heading"],
                "tokens": section["tokens"], "body": section["body"],
            }, indent=2, ensure_ascii=False))
            return
        print(f"\n📖 [{name}] section: {section['heading']}  (~{section['tokens']} tokens)\n")
        print(section["body"])
        return

    payload = {
        "skill": name,
        "kind": "skill",
        "path": doc["path"],
        "frontmatter": doc["frontmatter"],
        "body_tokens": doc["tokens"],
        "outline": skilldoc.outline(doc),
        "tools": [{"id": t["id"], "kind": t["kind"]} for t in tools],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"\n📖 [{name}]  ~{doc['tokens']} tokens, {len(doc['sections'])} sections, {len(tools)} tools")
    print(f"   {doc['path']}\n")
    print("   Sections:")
    for s in skilldoc.outline(doc):
        indent = "   " + "  " * s["level"]
        print(f"{indent}{s['heading'] or '(preamble)':<58} {s['tokens']:>5} tok")
    print(f"\n   Read one:  omnicli describe {name} --section \"<heading>\"")
    print(f"   Tool ids:  omnicli tools {name}")


def cmd_describe(tool_id: str, as_json: bool = False, section: str = "", doc: str = ""):
    """Return the exact input contract for ONE tool, or a skill's body."""
    con = _require_catalog()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        # A skill name gives the skill itself, checked before the legacy
        # "fall back to the skill's primary script" path.
        if con.execute("SELECT 1 FROM skills WHERE name = ?", (tool_id,)).fetchone():
            return _describe_skill(con, tool_id, section, as_json, doc)
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
        "enabled": bool(row["enabled"]),
        "summary": row["summary"],
        "path": row["path"],
        "argv": json.loads(row["argv"] or "[]"),
        "aliases": json.loads(skill["aliases"] or "[]") if skill else [],
        "contract": contract,
    }

    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    state = "enabled" if row["enabled"] else f"DISABLED (run `omnicli enable {row['id']}`)"
    print(f"\n📄 [omnicli describe] {row['id']}\n")
    print(f"   skill   : {row['skill']}")
    print(f"   kind    : {row['kind']}")
    print(f"   state   : {state}")
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

def cmd_invoke(tool_id: str, extra_args: list[str], out_path: str | None = None,
               project_fields: str | None = None, jq_expr: str | None = None,
               grep: str | None = None, max_bytes: int = DEFAULT_MAX_BYTES,
               as_json: bool = False, timeout: float = 300.0):
    con = _require_catalog()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        sys.exit(f"❌ Error: no tool named {tool_id!r}. "
                 f"Use `omnicli tools <skill>` to list a skill's tools.")

    # Discovery does not imply exposure. The catalog knows the tool; the
    # policy decides whether an agent may run it. `describe` still works, so
    # the contract can be reviewed before the gate is opened.
    if not row["enabled"]:
        sys.exit(f"❌ Error: tool {tool_id!r} is disabled.\n"
                 f"   Review it:  omnicli describe {tool_id}\n"
                 f"   Enable it:  omnicli enable {tool_id}")

    argv = json.loads(row["argv"] or "[]")
    cmd = invoke.build_cmd(argv, extra_args, python=sys.executable, skill_dir=SKILL_DIR)
    run = invoke.execute(cmd, timeout=timeout)

    fields = invoke.parse_fields(project_fields)
    # Reserve one byte for the newline that terminates a plain reply. The JSON
    # branch re-shapes against its measured envelope instead (fit_envelope).
    budget = max(0, max_bytes - (0 if as_json else 1))
    try:
        shaped = invoke.shape(
            run["stdout"], fields=fields, jq_expr=jq_expr,
            grep_pattern=grep, max_bytes=budget,
        )
    except re.error as exc:
        sys.exit(f"❌ Error: invalid --omni-grep pattern: {exc}")

    if shaped["projection_requested"] and not shaped["projection_applied"]:
        print("⚠️  omnicli: projection could not be applied "
              "(output was not JSON, or no requested field matched); "
              "returning the unfiltered payload.", file=sys.stderr)

    # The buffer preserves what the cap discards, so it holds the *unfiltered*
    # stdout, written before projection, grep and truncation.
    if out_path:
        p = Path(out_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(run["stdout"], encoding="utf-8")
        print(f"💾 Full stdout buffered to: {p}  ({shaped['raw_bytes']} bytes)")
        if shaped["projection_applied"] or shaped["grep_applied"]:
            print("📊 The preview below is filtered; the buffer is not.")
        print()

    if run["stderr"]:
        print(run["stderr"], file=sys.stderr, end="" if run["stderr"].endswith("\n") else "\n")

    if as_json:
        def build(shaped: dict[str, Any]) -> dict[str, Any]:
            payload = {
                "tool": tool_id,
                "exit_code": run["exit_code"],
                "bytes": shaped["bytes"],
                "raw_bytes": shaped["raw_bytes"],
                "truncated": shaped["truncated"],
                "projection_applied": shaped["projection_applied"],
                "output": shaped["output"],
            }
            if run["stderr"]:
                payload["stderr"] = run["stderr"][-2000:]
            return payload

        payload, encoded, _ = invoke.fit_envelope(
            run["stdout"], build, fields=fields, jq_expr=jq_expr,
            grep_pattern=grep, max_bytes=max_bytes,
        )
        if len(encoded.encode("utf-8")) > max_bytes:
            # The envelope itself cannot fit (very small cap). Say why in a
            # reply that does fit, rather than printing past the ceiling.
            sys.stdout.write(invoke.refusal(len(encoded.encode()), max_bytes) + "\n")
            sys.exit(1)
        sys.stdout.write(encoded + ("\n" if len(encoded.encode()) < max_bytes else ""))
        sys.exit(run["exit_code"])

    sys.stdout.write(shaped["output"])
    if not shaped["output"].endswith("\n") and shaped["bytes"] < budget:
        sys.stdout.write("\n")
    sys.exit(run["exit_code"])

# --------------------------------------------------------------------------
# policy — discovery does not imply exposure
# --------------------------------------------------------------------------

def _tool_row(con, tool_id: str):
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        sys.exit(f"❌ Error: no tool named {tool_id!r}. "
                 f"Use `omnicli tools <skill>` to list a skill's tools.")
    return row


def cmd_gate(tool_id: str | None, enabled: bool, as_json: bool = False,
             all_tools: bool = False):
    """Enable or disable a tool, recording the decision against its contract."""
    con = _require_catalog()
    if all_tools:
        rows = con.execute("SELECT id, contract, enabled FROM tools ORDER BY id").fetchall()
    elif tool_id:
        rows = [_tool_row(con, tool_id)]
    else:
        sys.exit("❌ Error: name a tool id, or pass --all.")

    changed = []
    for row in rows:
        if bool(row["enabled"]) == enabled:
            continue
        contract = json.loads(row["contract"] or "{}")
        policy.set_enabled(row["id"], enabled, contract=contract)
        con.execute("UPDATE tools SET enabled = ? WHERE id = ?",
                    (1 if enabled else 0, row["id"]))
        changed.append(row["id"])
    con.commit()

    verb = "enabled" if enabled else "disabled"
    if as_json:
        print(json.dumps({"action": verb, "changed": len(changed),
                          "tools": changed if not all_tools else None,
                          "scanned": len(rows)}, indent=2))
        return
    if all_tools:
        print(f"✅ {verb} {len(changed)} of {len(rows)} tools.")
    elif changed:
        print(f"✅ {verb} {changed[0]}")
    else:
        print(f"ℹ️  {rows[0]['id']} was already {verb}.")


def cmd_policy(tool_id: str | None = None, as_json: bool = False):
    """Show the gate: what is runnable, what is not, and why it changed."""
    con = _require_catalog()
    if tool_id:
        row = _tool_row(con, tool_id)
        payload = {
            "tool": tool_id,
            "enabled": bool(row["enabled"]),
            "decision": policy.entry(tool_id),
            "history": policy.history(tool_id),
        }
    else:
        rows = con.execute("SELECT id, skill, enabled FROM tools ORDER BY skill, id").fetchall()
        disabled = [r["id"] for r in rows if not r["enabled"]]
        payload = {
            "tools": len(rows),
            "enabled": len(rows) - len(disabled),
            "disabled": disabled,
            "recent_decisions": policy.history(limit=10),
        }

    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if tool_id:
        print(f"\n🔐 [omnicli policy] {tool_id}\n")
        print(f"   state: {'enabled' if payload['enabled'] else 'disabled'}")
        decision = payload["decision"]
        if decision:
            print(f"   since: {decision.get('at')}  contract:{decision.get('contract')}")
        if payload["history"]:
            print("   history:")
            for rec in payload["history"]:
                print(f"      {rec.get('at')}  {rec.get('before')} → {rec.get('after')}")
        print()
        return

    print(f"\n🔐 [omnicli policy] {payload['enabled']}/{payload['tools']} tools enabled\n")
    if payload["disabled"]:
        shown = payload["disabled"][:40]
        print("   disabled: " + ", ".join(shown)
              + (f" … (+{len(payload['disabled']) - len(shown)} more)"
                 if len(payload["disabled"]) > len(shown) else ""))
    for rec in payload["recent_decisions"]:
        print(f"   {rec.get('at')}  {rec.get('tool')}: {rec.get('before')} → {rec.get('after')}")
    print()


def cmd_alias(skill: str = None, aliases: str = None, tags: str = None,
              remove: bool = False, show_all: bool = False, as_json: bool = False):
    """Read or write a skill's curated routing metadata.

    The alias set is the routing surface of a skill: the words a user would
    type that appear in no document. It lives behind this command so that a
    publisher never needs to know where the file is.
    """
    if builder is None or aliases_mod is None:
        sys.exit("❌ Error: omnicli catalog package not importable.")

    if show_all or not skill:
        data = aliases_mod.load()
        if as_json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        print(f"\n🏷️  [curated routing metadata] {len(data)} skills\n")
        for name, rec in sorted(data.items()):
            al = rec.get("aliases", [])
            tg = rec.get("tags", [])
            flag = "  (body not indexed)" if rec.get("index_body") is False else ""
            print(f"  • {name}{flag}")
            if al:
                print(f"      aliases: {', '.join(al)}")
            if tg:
                print(f"      tags   : {', '.join(tg)}")
        print()
        return

    if remove:
        if aliases_mod.remove(skill):
            print(f"🗑️  Removed curated metadata for {skill}")
        else:
            print(f"ℹ️  No curated metadata for {skill}")
        return

    if aliases is None and tags is None:
        rec = aliases_mod.get(skill)
        if as_json:
            print(json.dumps(rec, indent=2, ensure_ascii=False))
            return
        if not rec:
            print(f"ℹ️  No curated metadata for {skill}")
            return
        print(f"\n🏷️  {skill}")
        print(f"   aliases: {', '.join(rec.get('aliases', [])) or '—'}")
        print(f"   tags   : {', '.join(rec.get('tags', [])) or '—'}")
        if rec.get("index_body") is False:
            print("   body    : not indexed (router skills opt out)")
        print()
        return

    al = [a for a in aliases.split(",")] if aliases is not None else None
    tg = [t for t in tags.split(",")] if tags is not None else None
    rec = aliases_mod.set_aliases(skill, al, tg)
    print(f"🏷️  {skill}: {len(rec.get('aliases', []))} aliases, "
          f"{len(rec.get('tags', []))} tags")
    print("   Reindex with `omnicli index --rebuild` to apply.")


# --------------------------------------------------------------------------
# index / eval
# --------------------------------------------------------------------------

def cmd_index(rebuild: bool = False, with_contracts: bool = True, as_json: bool = False,
              check: bool = False):
    con = builder.connect()

    if check:
        # Report freshness without doing any work. Used by the skill factory
        # to skip a rebuild when nothing changed.
        stale = builder.is_stale(con)
        version_ok = builder.meta_get(con, "schema_version") == builder.SCHEMA_VERSION
        fresh = (not stale) and version_ok
        payload = {
            "fresh": fresh,
            "stale": stale,
            "schema_version_ok": version_ok,
            "skills": int(builder.meta_get(con, "skill_count", "0") or 0),
            "tools": int(builder.meta_get(con, "tool_count", "0") or 0),
            "docs": int(builder.meta_get(con, "doc_count", "0") or 0),
            "built_at": float(builder.meta_get(con, "built_at", "0") or 0),
            "db": str(builder.db_path()),
        }
        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            state = "✅ fresh" if fresh else "⚠️  stale"
            print(f"{state}  {payload['skills']} skills · {payload['tools']} tools · "
                  f"{payload['docs']} docs")
            print(f"   {payload['db']}")
        sys.exit(0 if fresh else 1)

    t0 = time.monotonic()
    summary = builder.ensure_built(con, rebuild=rebuild, with_contracts=with_contracts, progress=True)
    elapsed = time.monotonic() - t0
    if as_json:
        summary["elapsed_seconds"] = round(elapsed, 3)
        print(json.dumps(summary, indent=2))
        return
    verb = "rebuilt" if summary.get("rebuilt") else "up to date"
    extracted = summary.get("contracts_extracted", 0)
    detail = f" · {extracted} contracts extracted" if extracted else " · 0 contracts extracted (cached)"
    print(f"\n📇 Catalog {verb}: {summary['skills']} skills · {summary['tools']} tools · "
          f"{summary['docs']} docs{detail}")
    print(f"   {builder.db_path()}")
    print(f"   {elapsed * 1000:.0f} ms\n")


def cmd_eval(verbose: bool = False, as_json: bool = False, rerank: str = "never"):
    runner = SKILL_DIR / "tests" / "eval_runner.py"
    if not runner.is_file():
        sys.exit("❌ Error: tests/eval_runner.py not found next to omnicli.")
    args = [sys.executable, str(runner), f"--rerank={rerank}"]
    if verbose:
        args.append("--verbose")
    if as_json:
        args.append("--json")
    sys.exit(subprocess.run(args).returncode)


# --------------------------------------------------------------------------
# mcp
# --------------------------------------------------------------------------

def cmd_mcp(as_json: bool = False):
    server = SKILL_DIR / "scripts" / "mcp_server.py"
    if not server.is_file():
        sys.exit("❌ Error: scripts/mcp_server.py not found next to omnicli.")
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
    p.add_argument("--rerank", choices=["auto", "always", "never"], default="auto",
                   help="auto=only re-rank when the lexical ranking is unsure (default), "
                        "always=re-rank every query, never=never re-rank")
    p.add_argument("--chunks", action="store_true",
                   help="With --json: include every matching chunk (default is the "
                        "compact routing view: skill, score, why, top hit)")

    p = sub.add_parser("list", help="List every skill in the registry")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="Include sidelined and archived skills")

    p = sub.add_parser("tools", help="List the tools belonging to a skill")
    p.add_argument("skill")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("describe", help="Show the exact input contract for ONE tool, or a skill's body")
    p.add_argument("tool_id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--section", default="", help="With a skill name: the heading of the section to read")
    p.add_argument("--doc", default="", help="With a skill name: the path or title of a document to read")

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

    p = sub.add_parser("enable", help="Expose a discovered tool to agents (gate)")
    p.add_argument("tool_id", nargs="?")
    p.add_argument("--all", action="store_true", help="Enable every catalogued tool")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("disable", help="Withdraw a tool without deleting it")
    p.add_argument("tool_id", nargs="?")
    p.add_argument("--all", action="store_true", help="Disable every tool")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("policy", help="Show the enable gate and its audit log")
    p.add_argument("tool_id", nargs="?")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("index", help="Build or refresh the catalog index")
    p.add_argument("--rebuild", action="store_true", help="Force a full rebuild")
    p.add_argument("--no-contracts", action="store_true", help="Skip --help contract extraction")
    p.add_argument("--check", action="store_true",
                   help="Report whether the index is fresh, without rebuilding")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("alias", help="Read or write a skill's curated routing metadata")
    p.add_argument("skill", nargs="?", help="Skill name; omit with --list to show all")
    p.add_argument("--aliases", default=None, help="Comma-separated alias list (replaces)")
    p.add_argument("--tags", default=None, help="Comma-separated tag list (replaces)")
    p.add_argument("--remove", action="store_true", help="Delete a skill's curated metadata")
    p.add_argument("--list", action="store_true", help="Show every skill's curated metadata")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("eval", help="Run the golden routing evaluation")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--rerank", choices=["auto", "always", "never"], default="never",
                   help="re-ranker mode used during the eval (default: never; the "
                        "catalog's own default is auto)")

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
                   explain=args.explain, no_rerank=args.no_rerank,
                   rerank=args.rerank, chunks=args.chunks)
    elif args.action == "list":
        cmd_list(as_json=args.json, show_all=args.all)
    elif args.action == "tools":
        cmd_tools(args.skill, as_json=args.json)
    elif args.action == "describe":
        cmd_describe(args.tool_id, as_json=args.json, section=args.section, doc=args.doc)
    elif args.action == "index":
        cmd_index(rebuild=args.rebuild, with_contracts=not args.no_contracts,
                  as_json=args.json, check=args.check)
    elif args.action == "enable":
        cmd_gate(args.tool_id, True, as_json=args.json, all_tools=args.all)
    elif args.action == "disable":
        cmd_gate(args.tool_id, False, as_json=args.json, all_tools=args.all)
    elif args.action == "policy":
        cmd_policy(args.tool_id, as_json=args.json)
    elif args.action == "alias":
        cmd_alias(skill=args.skill, aliases=args.aliases, tags=args.tags,
                  remove=args.remove, show_all=args.list, as_json=args.json)
    elif args.action == "eval":
        cmd_eval(verbose=args.verbose, as_json=args.json, rerank=args.rerank)
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
