#!/usr/bin/env python3
"""Run a task against OpenCode Go with a small tool loop.

The cloud subagent used to depend on OpenRouter. This talks to the Go
inference endpoint instead, in the OpenAI shape, and gives the model four
tools: read, write, list, bash. It edits the checkout it is run in and stops.

    OPENCODE_GO_TOKEN=... OPENCODE_GO_MODEL=deepseek-v4.1-flash \
      python3 go_agent.py --task "add a docstring to ports.py ..."

Environment:
    OPENCODE_GO_TOKEN   bearer token for opencode.ai (required)
    OPENCODE_GO_MODEL   model id without the provider prefix (default deepseek-v4.1-flash)
    OPENCODE_GO_URL     endpoint override
    OPENCODE_GO_TURNS   max model turns (default 24)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_URL = "https://opencode.ai/inference/go/openai/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4.1-flash"
SYSTEM = (
    "You are a coding subagent working alone in a git checkout. "
    "Be economical: you have a hard turn budget, so spend at most half of it "
    "gathering evidence and then write your output, even if it is incomplete. "
    "You have read_file, write_file, list_dir, run_bash and finish. "
    "Make the smallest change that satisfies the task, then run the project's own "
    "tests if they are quick. Never run git push, git checkout or sudo. "
    "When you are done, call finish with a one-paragraph summary of what changed."
)
BASH_DENY = ("git push", "git checkout", "git reset", "sudo", "rm -rf /", "shutdown", "reboot")

# The Go catalog serves three protocols. This runner speaks the OpenAI chat
# shape, so these ids must be driven elsewhere or by a different client.
ANTHROPIC_SHAPE = {"claude-haiku-5-5", "minimax-m3", "qwen3.8-max", "qwen3.8-flash", "qwen3.7-plus"}
RESPONSES_SHAPE = {
    "grok-4.7",
    "gpt-6-luna",
    "gpt-5.6-luna",
    "muse-spark-1.3-contributor",
    "muse-spark-1.2-contributor",
}
SUGGEST = {
    "anthropic": "minimax-m3.1-flash, glm-5.3, or deepseek-v4-pro",
    "responses": "deepseek-v4.1-flash, kimi-k3, or glm-5.3-flash",
}


def tools() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 file from the checkout.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a whole UTF-8 file. Creates parent directories.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "List a directory, one entry per line.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_bash",
                "description": "Run one shell command in the checkout and return its output.",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Stop and report. Call this when the task is done or blocked.",
                "parameters": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
            },
        },
    ]


def call_model(url: str, token: str, model: str, session: str, messages: list) -> dict:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "tools": tools(),
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 4000,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-opencode-session": session,
            # The Go docs ask clients to identify themselves rather than
            # sending a library user agent, which a bot filter can reject.
            "User-Agent": "opencode-go-subagent/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def run_bash(command: str, root: Path) -> str:
    lowered = command.lower()
    for denied in BASH_DENY:
        if denied in lowered:
            return f"refused: '{denied}' is not allowed in a subagent"
    guard = shutil.which("guard-hooks")
    if guard:
        verdict = subprocess.run([guard, "check", command], capture_output=True, text=True)
        if verdict.returncode != 0:
            return f"refused by guard-hooks: {(verdict.stderr or verdict.stdout).strip()[:300]}"
    try:
        proc = subprocess.run(command, shell=True, cwd=root, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "timed out after 300s"
    output = (proc.stdout or "") + (proc.stderr or "")
    return f"exit {proc.returncode}\n{output[-6000:]}"


def safe_path(raw: str, root: Path) -> tuple[Path | None, str]:
    if raw in ("", ".", "/", "./"):
        return None, "refused: give a file path, not the checkout root"
    path = (root / raw).resolve()
    if not str(path).startswith(str(root.resolve())):
        return None, "refused: path escapes the checkout"
    return path, ""


def dispatch(name: str, args: dict, root: Path) -> tuple[str, bool]:
    if name == "read_file":
        path, why = safe_path(args.get("path", ""), root)
        if path is None:
            return why, False
        if not path.is_file():
            return f"no such file: {args.get('path')}", False
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:12000], False
        except OSError as exc:
            return f"could not read {args.get('path')}: {exc}", False
    if name == "write_file":
        path, why = safe_path(args.get("path", ""), root)
        if path is None:
            return why, False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.get("content", ""), encoding="utf-8")
        except OSError as exc:
            return f"could not write {args.get('path')}: {exc}", False
        return f"wrote {path.relative_to(root.resolve())} ({len(args.get('content', ''))} chars)", False
    if name == "list_dir":
        path = root if args.get("path", ".") in ("", ".", "/") else (root / args["path"]).resolve()
        if not path.is_dir():
            return f"no such directory: {args.get('path')}", False
        try:
            return "\n".join(sorted(p.name for p in path.iterdir()))[:4000], False
        except OSError as exc:
            return f"could not list {args.get('path')}: {exc}", False
    if name == "run_bash":
        return run_bash(args.get("command", ""), root), False
    if name == "finish":
        return args.get("summary", ""), True
    return f"unknown tool: {name}", False


def changed(expect: str, root: Path) -> bool:
    proc = subprocess.run(["git", "status", "--porcelain", "--", expect], cwd=root, capture_output=True, text=True)
    return bool(proc.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCode Go subagent loop")
    parser.add_argument("--task", default=os.environ.get("TASK"), help="task prompt (default $TASK)")
    parser.add_argument("--root", default=".", help="checkout to work in")
    parser.add_argument("--model", default=os.environ.get("OPENCODE_GO_MODEL", DEFAULT_MODEL))
    parser.add_argument("--turns", type=int, default=int(os.environ.get("OPENCODE_GO_TURNS", "24")))
    parser.add_argument("--url", default=os.environ.get("OPENCODE_GO_URL", DEFAULT_URL))
    parser.add_argument(
        "--expect-change",
        default=os.environ.get("OPENCODE_GO_EXPECT_PATH", ""),
        help="path that must be modified or created, or the run fails",
    )
    args = parser.parse_args()

    token = os.environ.get("OPENCODE_GO_TOKEN", "").strip()
    if not token:
        print("error: OPENCODE_GO_TOKEN is not set", file=sys.stderr)
        return 2
    if not args.task:
        print("error: no task given (--task or $TASK)", file=sys.stderr)
        return 2

    if args.model in ANTHROPIC_SHAPE or args.model in RESPONSES_SHAPE:
        shape = "anthropic" if args.model in ANTHROPIC_SHAPE else "responses"
        print(
            f"error: {args.model} is not served in the OpenAI chat shape, which is the "
            f"only protocol this runner speaks (it needs the {shape} API).\n"
            f"       OpenAI-compatible alternatives: {SUGGEST[shape]}",
            file=sys.stderr,
        )
        return 2

    root = Path(args.root).resolve()
    session = f"subagent-{uuid.uuid4()}"
    messages = [
        {"role": "system", "content": f"{SYSTEM} You have at most {args.turns} turns."},
        {"role": "user", "content": args.task},
    ]

    for turn in range(1, args.turns + 1):
        try:
            body = call_model(args.url, token, args.model, session, messages)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            print(f"[turn {turn}] HTTP {exc.code}: {detail}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001 - the workflow needs the reason
            print(f"[turn {turn}] model call failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        if body.get("error"):
            print(f"[turn {turn}] provider error: {body['error']}", file=sys.stderr)
            return 1

        nudge_at = max(2, (args.turns * 2) // 3)
        if turn == nudge_at and not any("Stop gathering" in str(m.get("content")) for m in messages):
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Turn {turn} of {args.turns}. Stop gathering evidence now and write the "
                        "deliverable with what you have. Partial and honest beats complete and late."
                    ),
                }
            )

        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        if message.get("content"):
            print(f"[turn {turn}] {message['content'][:400]}")
        if not calls:
            print(
                f"[turn {turn}] stopped without calling finish — treating the run as failed "
                "(the model answered in prose instead of acting)",
                file=sys.stderr,
            )
            return 1

        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        finished = False
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                call_args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                call_args = {}
            result, finished = dispatch(name, call_args, root)
            label = call_args.get("path") or call_args.get("command") or ""
            print(f"[turn {turn}] {name} {str(label)[:80]} -> {str(result).splitlines()[0][:120]}")
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
            if finished:
                print(f"\nfinished: {result}")
                if args.expect_change and not changed(args.expect_change, root):
                    print(
                        f"error: the run finished but {args.expect_change} was not modified",
                        file=sys.stderr,
                    )
                    return 1
                return 0

    print(
        f"stopped after {args.turns} turns without finishing; raise OPENCODE_GO_TURNS "
        f"or narrow the task",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
