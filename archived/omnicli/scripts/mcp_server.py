"""omnicli MCP server — Face B of the Uber OmniCLI.

Speaks JSON-RPC 2.0 over stdio and exposes exactly four meta-tools. The
point is that a JSON-RPC tool-calling agent never sees the workstation's
hundreds of executables; it sees four tiny tools and pulls the contract for
one real tool at a time.

    omni_discover  intent -> ranked tool/skill ids, one line each, no schemas
    omni_describe  tool_id -> the exact input contract for that one tool
    omni_invoke    tool_id + args -> a bounded, projected result
    omni_status    -> endpoint health, catalog freshness, retrieval tier

Transport is hand-rolled rather than using the official SDK: the subset
needed here is small and stable, it keeps the control plane dependency-free,
and it matches the stdlib-only discipline of the rest of the catalog. The
method dispatch below is the only place that would change if the SDK were
adopted later.

Protocol notes:
  * MCP uses newline-delimited JSON-RPC over stdio (one JSON object per line).
  * `initialize` must be answered with a `protocolVersion`, `capabilities`
    and `serverInfo`.
  * Tool results are returned as `content: [{type: "text", text: ...}]`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

from catalog import builder, search  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "omnicli"
SERVER_VERSION = "1.0.0"

DEFAULT_MAX_BYTES = 8000


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _con():
    con = builder.connect()
    builder.ensure_built(con, progress=False)
    return con


def _text_result(payload: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": payload}],
        "isError": is_error,
    }


def _json_result(payload: Any) -> dict[str, Any]:
    return _text_result(json.dumps(payload, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------
# meta-tool implementations
# --------------------------------------------------------------------------

def tool_discover(args: dict[str, Any]) -> dict[str, Any]:
    """Rank skills and tools for a natural-language intent."""
    intent = (args.get("intent") or "").strip()
    limit = int(args.get("limit") or 8)
    if not intent:
        return _json_result({"error": "intent is required"})

    con = _con()
    res = search.search(con, intent, limit=limit, rerank_enabled=not args.get("no_rerank"))

    skills = []
    for r in res["results"]:
        tools = con.execute(
            "SELECT id, kind, summary FROM tools WHERE skill = ? ORDER BY id LIMIT 8",
            (r["skill"],),
        ).fetchall()
        skills.append({
            "skill": r["skill"],
            "score": r["score"],
            "why": r["chunks"][0]["snippet"][:180] if r["chunks"] else "",
            "tools": [{"id": t["id"], "kind": t["kind"], "summary": (t["summary"] or "")[:120]}
                      for t in tools],
        })

    return _json_result({
        "intent": intent,
        "tier": res["tier"],
        "next": "Call omni_describe with one of the tool ids above to get its input contract.",
        "results": skills,
    })


def tool_describe(args: dict[str, Any]) -> dict[str, Any]:
    """Return the exact input contract for a single tool, or a skill's body.

    A tool id gives that tool's usage, flags, positionals and subcommands.
    A skill name gives the skill itself: its frontmatter and a section
    outline, so the agent can pull one section rather than the whole body.
    """
    tool_id = (args.get("tool_id") or "").strip()
    if not tool_id:
        return _json_result({"error": "tool_id is required"})
    section_name = (args.get("section") or "").strip()
    doc_name = (args.get("doc") or "").strip()

    con = _con()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        # A skill name gives the skill itself. This is checked before the
        # legacy "fall back to the skill's primary script" path, because a
        # skill name and a script contract are different things and the
        # caller asked for the skill.
        if con.execute("SELECT 1 FROM skills WHERE name = ?", (tool_id,)).fetchone():
            if doc_name:
                return _describe_doc(con, tool_id, doc_name)
            return _describe_skill(con, tool_id, section_name)
        cands = con.execute(
            "SELECT id FROM tools WHERE skill = ? AND kind = 'script' LIMIT 1", (tool_id,)
        ).fetchall()
        if cands:
            row = con.execute("SELECT * FROM tools WHERE id = ?", (cands[0]["id"],)).fetchone()
        else:
            return _text_result(f"No tool or skill named {tool_id!r}.", is_error=True)

    contract = json.loads(row["contract"] or "{}")
    return _json_result({
        "id": row["id"],
        "skill": row["skill"],
        "kind": row["kind"],
        "summary": row["summary"],
        "argv": json.loads(row["argv"] or "[]"),
        "contract": contract,
        "next": f"Call omni_invoke with tool_id={row['id']!r} and your arguments.",
    })


def _describe_doc(con, name: str, query: str) -> dict[str, Any]:
    """Read one document the skill declared as part of its searchable body."""
    from pathlib import Path as _Path

    q = (query or "").strip().lower()
    rows = con.execute(
        "SELECT title, path, body FROM docs WHERE skill = ? AND kind = 'doc'", (name,)
    ).fetchall()
    if not rows:
        return _text_result(
            f"Skill {name!r} declares no documents. Call omni_describe with "
            f"tool_id={name!r} to see the skill itself.", is_error=True)

    scored = []
    for title, path, body in rows:
        t = (title or "").lower()
        p = (path or "").lower()
        stem = _Path(p).stem.lower()
        rel = p.split("/suites/")[-1] if "/suites/" in p else p
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
        return _text_result(f"No document matching {query!r} in {name!r}.", is_error=True)

    scored.sort(key=lambda r: -r[0])
    _, title, path, body = scored[0]
    return _json_result({
        "skill": name,
        "title": title,
        "path": path,
        "tokens": len(body) // 4,
        "body": body,
    })


def _describe_skill(con, name: str, section_name: str) -> dict[str, Any]:
    """A skill id: frontmatter + outline, or one section on request."""
    from catalog import skilldoc

    row = con.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
    if row is None:
        return _text_result(f"No tool or skill named {name!r}.", is_error=True)
    md_path = row["md_path"]
    if not md_path or not Path(md_path).is_file():
        return _text_result(f"Skill {name!r} has no readable SKILL.md.", is_error=True)

    doc = skilldoc.load_skill_doc(md_path)
    front = doc["frontmatter"]

    if section_name:
        section = skilldoc.pick_section(doc, section_name)
        if section is None:
            return _text_result(
                f"No section {section_name!r} in {name!r}. Available: "
                + ", ".join(s["heading"] for s in doc["sections"] if s["heading"]),
                is_error=True,
            )
        return _json_result({
            "skill": name,
            "section": section["heading"],
            "tokens": section["tokens"],
            "body": section["body"],
            "next": "Call omni_discover or omni_describe for anything else you need.",
        })

    tools = con.execute(
        "SELECT id, kind FROM tools WHERE skill = ? ORDER BY kind, id", (name,)
    ).fetchall()
    return _json_result({
        "skill": name,
        "kind": "skill",
        "path": doc["path"],
        "frontmatter": front,
        "body_tokens": doc["tokens"],
        "outline": skilldoc.outline(doc),
        "tools": [{"id": t["id"], "kind": t["kind"]} for t in tools],
        "next": (
            f"Call omni_describe with tool_id={name!r} and section=\"<heading>\" to read "
            f"one section, or omni_describe with a tool id for its input contract."
        ),
    })


def tool_invoke(args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool and return a bounded result."""
    tool_id = (args.get("tool_id") or "").strip()
    if not tool_id:
        return _json_result({"error": "tool_id is required"})

    con = _con()
    row = con.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        return _text_result(f"No tool named {tool_id!r}.", is_error=True)

    argv = json.loads(row["argv"] or "[]")
    cmd = [str(a).replace("{python}", sys.executable).replace("{skill}", str(SKILL_DIR))
           for a in argv]
    cmd += [str(a) for a in (args.get("args") or [])]

    import subprocess
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=float(args.get("timeout") or 300.0))
        raw = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        code = proc.returncode
    except subprocess.TimeoutExpired:
        raw, code = "omnicli: tool timed out", 124
    except OSError as exc:
        raw, code = f"omnicli: failed to execute: {exc}", 127

    projection = args.get("projection")
    if projection:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                raw = json.dumps({k: v for k, v in data.items() if k in projection}, indent=2)
        except (ValueError, TypeError):
            pass

    max_bytes = int(args.get("max_bytes") or DEFAULT_MAX_BYTES)
    data = raw.encode("utf-8", errors="replace")
    truncated = len(data) > max_bytes
    if truncated:
        raw = data[:max_bytes].decode("utf-8", errors="ignore") + "\n… [omnicli] output capped."

    return _json_result({
        "tool": tool_id,
        "exit_code": code,
        "bytes": len(data),
        "truncated": truncated,
        "output": raw,
    })


def tool_status(args: dict[str, Any]) -> dict[str, Any]:
    """Endpoint health, catalog freshness, and the active retrieval tier."""
    import socket

    def online(port: int) -> bool:
        for host in ("127.0.0.1", "100.83.178.106"):
            try:
                with socket.create_connection((host, port), timeout=0.35):
                    return True
            except OSError:
                continue
        return False

    ports = {8080: "Genesis 35B LLM", 8081: "audio.cpp ASR/TTS", 8083: "vllm-d3-mini decisions",
             8085: "LightOnOCR", 8087: "embeddings (optional re-ranker)", 8089: "OneJev fallback"}

    con = _con()
    built = con.execute("SELECT count(*) AS c FROM skills").fetchone()["c"]
    tier = "bm25+rerank" if search.embedding_available() else "bm25"

    return _json_result({
        "services": {f":{p}": {"name": n, "online": online(p)} for p, n in ports.items()},
        "catalog": {
            "skills": built,
            "tools": con.execute("SELECT count(*) AS c FROM tools").fetchone()["c"],
            "docs": con.execute("SELECT count(*) AS c FROM docs").fetchone()["c"],
            "built_at": builder.meta_get(con, "built_at"),
        },
        "retrieval_tier": tier,
    })


# --------------------------------------------------------------------------
# tool manifest
# --------------------------------------------------------------------------

TOOLS = [
    {
        "name": "omni_discover",
        "description": (
            "Find the right tool for a natural-language intent. Returns ranked skill "
            "names with their tool ids and a one-line reason. Start here. Call "
            "omni_describe with a returned skill name for that skill's section "
            "outline, or with a tool id for its input contract."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "What you want to do, in plain language."},
                "limit": {"type": "integer", "description": "Max results (default 8).", "default": 8},
                "no_rerank": {"type": "boolean", "description": "Skip the optional embedding re-ranker."},
                "rerank": {
                    "type": "string",
                    "enum": ["auto", "always", "never"],
                    "description": "Re-ranker mode. auto (default) only re-ranks when the "
                                   "lexical ranking is unsure.",
                },
            },
            "required": ["intent"],
        },
    },
    {
        "name": "omni_describe",
        "description": (
            "Get the exact input contract for ONE tool: usage, flags, positionals and "
            "subcommands. Call this before invoking. Only one tool's contract is "
            "returned per call. Given a skill name instead of a tool id, returns the "
            "skill's frontmatter and section outline; add section=\"<heading>\" to "
            "read that one section of its body, or doc=\"<path>\" to read one of the "
            "documents the skill declares as searchable (rubrics, playbooks, guides)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_id": {"type": "string", "description": "A tool id from omni_discover, or a skill name."},
                "section": {
                    "type": "string",
                    "description": "Optional. Heading of the skill section to read.",
                },
                "doc": {
                    "type": "string",
                    "description": "Optional. Path or title of a document the skill declares, e.g. \"pstack/playbooks/hillclimb.md\".",
                },
            },
            "required": ["tool_id"],
        },
    },
    {
        "name": "omni_invoke",
        "description": (
            "Execute a tool. Output is always bounded by max_bytes and can be "
            "projected down to specific JSON fields, so a large payload never floods "
            "the context window."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_id": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"},
                         "description": "Command-line arguments for the tool."},
                "projection": {"type": "array", "items": {"type": "string"},
                               "description": "JSON fields to keep from the result."},
                "max_bytes": {"type": "integer", "description": "Hard cap on returned bytes."},
                "timeout": {"type": "number", "description": "Seconds before the tool is killed."},
            },
            "required": ["tool_id"],
        },
    },
    {
        "name": "omni_status",
        "description": (
            "Report which local inference services are online, how fresh the tool "
            "catalog is, and which retrieval tier search is currently running "
            "(bm25 or bm25+rerank)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

HANDLERS = {
    "omni_discover": tool_discover,
    "omni_describe": tool_describe,
    "omni_invoke": tool_invoke,
    "omni_status": tool_status,
}


# --------------------------------------------------------------------------
# JSON-RPC plumbing
# --------------------------------------------------------------------------

def respond(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def respond_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method")
    msg_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return respond(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "omnicli exposes this workstation's tools through four meta-tools. "
                "Call omni_discover with a plain-language intent, then omni_describe "
                "for the single tool you want, then omni_invoke."
            ),
        })

    if method in ("notifications/initialized", "initialized"):
        return None  # notification, no response

    if method == "ping":
        return respond(msg_id, {})

    if method == "tools/list":
        return respond(msg_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return respond_error(msg_id, -32602, f"Unknown tool: {name}")
        try:
            result = handler(params.get("arguments") or {})
        except Exception as exc:  # pragma: no cover - surface errors, never crash the loop
            result = _text_result(f"omnicli error in {name}: {exc}", is_error=True)
        return respond(msg_id, result)

    if method == "shutdown":
        return respond(msg_id, {})

    if msg_id is None:
        return None  # any other notification

    return respond_error(msg_id, -32601, f"Method not found: {method}")


def serve() -> None:
    """Read newline-delimited JSON-RPC from stdin, write replies to stdout."""
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            out.write(json.dumps(respond_error(None, -32700, "Parse error")) + "\n")
            out.flush()
            continue
        if not isinstance(req, dict):
            continue
        reply = handle(req)
        if reply is not None:
            out.write(json.dumps(reply, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    try:
        serve()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
