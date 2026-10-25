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
    OPENCODE_GO_TURNS   max model turns (default 12)
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
    "You have read_file, write_file, list_dir, run_bash and finish. "
    "Make the smallest change that satisfies the task, then run the project's own "
    "tests if they are quick. Never run git push, git checkout or sudo. "
    "When you are done, call finish with a one-paragraph summary of what changed."
)
BASH_DENY = ("git push", "git checkout", "git reset", "sudo", "rm -rf /", "shutdown", "reboot")


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


def dispatch(name: str, args: dict, root: Path) -> tuple[str, bool]:
    if name == "read_file":
        path = (root / args.get("path", "")).resolve()
        if not str(path).startswith(str(root.resolve())):
            return "refused: path escapes the checkout", False
        if not path.is_file():
            return f"no such file: {args.get('path')}", False
        return path.read_text(encoding="utf-8", errors="replace")[:12000], False
    if name == "write_file":
        path = (root / args.get("path", "")).resolve()
        if not str(path).startswith(str(root.resolve())):
            return "refused: path escapes the checkout", False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.get("content", ""), encoding="utf-8")
        return f"wrote {path.relative_to(root.resolve())} ({len(args.get('content', ''))} chars)", False
    if name == "list_dir":
        path = (root / args.get("path", ".")).resolve()
        if not path.is_dir():
            return f"no such directory: {args.get('path')}", False
        return "\n".join(sorted(p.name for p in path.iterdir()))[:4000], False
    if name == "run_bash":
        return run_bash(args.get("command", ""), root), False
    if name == "finish":
        return args.get("summary", ""), True
    return f"unknown tool: {name}", False


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCode Go subagent loop")
    parser.add_argument("--task", default=os.environ.get("TASK"), help="task prompt (default $TASK)")
    parser.add_argument("--root", default=".", help="checkout to work in")
    parser.add_argument("--model", default=os.environ.get("OPENCODE_GO_MODEL", DEFAULT_MODEL))
    parser.add_argument("--turns", type=int, default=int(os.environ.get("OPENCODE_GO_TURNS", "12")))
    parser.add_argument("--url", default=os.environ.get("OPENCODE_GO_URL", DEFAULT_URL))
    args = parser.parse_args()

    token = os.environ.get("OPENCODE_GO_TOKEN", "").strip()
    if not token:
        print("error: OPENCODE_GO_TOKEN is not set", file=sys.stderr)
        return 2
    if not args.task:
        print("error: no task given (--task or $TASK)", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    session = f"subagent-{uuid.uuid4()}"
    messages = [
        {"role": "system", "content": SYSTEM},
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

        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        if message.get("content"):
            print(f"[turn {turn}] {message['content'][:400]}")
        if not calls:
            print(f"[turn {turn}] no tool call; stopping")
            return 0 if turn > 1 else 1

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
                return 0

    print(f"stopped after {args.turns} turns without finishing", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
