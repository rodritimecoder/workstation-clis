"""Generate the Python binding module used by `omnicli exec`.

The bindings are deliberately thin: every call shells out to the `omnicli`
CLI, so a plan inherits the enable gate, field projection, byte cap and disk
buffer rather than reimplementing them. What the sandbox buys is not a second
policy engine — it is the ability to keep intermediate values in variables
instead of the model's context window.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

MODULE = '''"""omnicli bindings — generated file, do not edit.

One plan, one turn. `search()` picks a tool by intent, `describe()` returns
one contract, `invoke()` runs it. Intermediate values stay in Python
variables; only what you print comes back to the model.

Every call goes through the `omnicli` CLI, so the enable gate, projection,
byte cap and buffer behave exactly as they do from the shell.
"""

from __future__ import annotations

import json
import os
import subprocess

OMNICLI = os.environ.get("OMNICLI_BIN", "omnicli")
TOOL_IDS = __TOOL_IDS__


def _log(event):
    path = os.environ.get("OMNICLI_TRACE")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\\n")


def _run(argv):
    _log({"call": argv[1] if len(argv) > 1 else "", "tool": argv[2] if len(argv) > 2 else ""})
    return subprocess.run(argv, capture_output=True, text=True)


def search(intent, limit=6):
    """Route by intent. Returns compact rows: skill, score, matched, why."""
    proc = _run([OMNICLI, "search", intent, "--json", "--limit", str(limit)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "search failed")
    return json.loads(proc.stdout).get("results", [])


def skills():
    """Every skill the catalog knows about."""
    proc = _run([OMNICLI, "list", "--json"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "list failed")
    return json.loads(proc.stdout)


def tools(skill):
    """The executable tools inside one skill."""
    proc = _run([OMNICLI, "tools", skill, "--json"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "tools failed")
    return json.loads(proc.stdout)


def describe(tool_id):
    """One tool's exact contract (usage, flags, state)."""
    proc = _run([OMNICLI, "describe", tool_id, "--json"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "describe failed")
    return json.loads(proc.stdout)


def invoke(tool_id, *args, project=None, grep=None, max_bytes=None, timeout=300.0):
    """Run one enabled tool. Returns the CLI envelope: output, exit_code, bytes."""
    argv = [OMNICLI, "invoke", tool_id, *[str(a) for a in args], "--omni-json"]
    if project:
        argv += ["--omni-project", project]
    if grep:
        argv += ["--omni-grep", grep]
    if max_bytes is not None:
        argv += ["--omni-max-bytes", str(max_bytes)]
    argv += ["--omni-timeout", str(timeout)]
    proc = _run(argv)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or f"{tool_id} failed")
    return json.loads(proc.stdout)


def output(tool_id, *args, **kwargs):
    """invoke() and return only the shaped stdout, not the envelope."""
    return invoke(tool_id, *args, **kwargs).get("output", "")
'''


def _omnicli_command() -> str:
    return shutil.which("omnicli") or "omnicli"


def bindings_dir() -> Path:
    return Path.home() / ".local" / "share" / "omnicli" / "bindings"


def module_source(con: sqlite3.Connection) -> str:
    ids = [row[0] for row in con.execute("SELECT id FROM tools ORDER BY id")]
    return MODULE.replace("__TOOL_IDS__", json.dumps(ids, ensure_ascii=False, indent=0))


def write(con: sqlite3.Connection, out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else bindings_dir()
    out.mkdir(parents=True, exist_ok=True)
    (out / "omnicli_tools.py").write_text(module_source(con), encoding="utf-8")
    return out


def ensure(con: sqlite3.Connection, fingerprint: str, out_dir: Path | None = None) -> Path:
    """Write the module when the catalog fingerprint changed, else reuse it."""
    out = Path(out_dir) if out_dir else bindings_dir()
    marker = out / ".fingerprint"
    module = out / "omnicli_tools.py"
    if module.is_file() and marker.is_file() and marker.read_text().strip() == fingerprint:
        return out
    write(con, out)
    marker.write_text(fingerprint, encoding="utf-8")
    return out
