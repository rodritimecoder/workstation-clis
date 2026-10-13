#!/usr/bin/env python3
"""Interactive REPL for JPT-4B typed decisions (llama.cpp + Vulkan, one model load).

    jev-style line format:   state | question | options
    options: {"name": "description", ...}   -> choice
              ["low", "mid", "high"]        -> score
              (none)                        -> noul, P(true)
    @file.txt reads the state from a file (text only — no images).

Commands: :info  :api  :gpu  :quit

This REPL talks to the llama-server started by start-jpt.sh; the model is not reloaded here.
The same decisions are available as JSON from the System One API (see :api).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jpt_llamacpp import JPTError, JPTLlamaCpp  # noqa: E402

ENGINE_URL = os.environ.get("JPT_ENGINE_URL", "http://127.0.0.1:8090")
API_PORT = os.environ.get("JPT_PORT", "8080")

BANNER = """JPT-4B — typed decisions (stock llama.cpp, Vulkan)
model : {model}
state | question | options     (JSON object = choice, JSON array = score, none = noul/P(true))
         @file.txt reads the state from a file
cmds   :info  :api  :gpu  :quit
"""


def parse_options(text):
    text = text.strip()
    if not text or text.lower() in ("none", "-", "null"):
        return None
    if text.startswith("{"):
        return json.loads(text)
    if text.startswith("["):
        return json.loads(text)
    return [p.strip() for p in text.split(",") if p.strip()]


def build_state(text):
    """@path references are inlined as file contents (text states only)."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@") and pathlib.Path(stripped[1:]).is_file():
            lines.append(pathlib.Path(stripped[1:]).read_text(errors="replace"))
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def main():
    engine = JPTLlamaCpp(ENGINE_URL)
    if not engine.health():
        sys.exit(f"llama-server not healthy at {ENGINE_URL} — run start-jpt.sh (or the desktop icon)")
    print(BANNER.format(model=engine.info()["model"]), flush=True)

    while True:
        try:
            line = input("jpt> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith(":"):
            cmd = line[1:].strip().lower()
            if cmd in ("quit", "exit", "q"):
                break
            if cmd == "info":
                print(json.dumps(engine.info(), indent=1), "\n")
            elif cmd == "api":
                print(f"curl http://127.0.0.1:{API_PORT}/v1/systemone "
                      f"-H 'Content-Type: application/json' -d @questions.json\n")
            elif cmd == "gpu":
                subprocess.run(["bash", "-lc",
                                "rocm-smi --showuse --showmeminfo vram 2>/dev/null | head -20 "
                                "|| nvidia-smi 2>/dev/null || echo 'no GPU tool'"])
            else:
                print("commands: :info  :api  :gpu  :quit\n")
            continue

        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) < 2:
            print("need: state | question | options\n")
            continue
        state = build_state(parts[0])
        question_text = parts[1]
        options = parse_options(parts[2]) if len(parts) > 2 else None

        if options is None:
            q = {"type": "noul", "instructions": question_text}
        elif isinstance(options, dict):
            q = {"type": "choice", "instructions": question_text,
                 "criteria": {k: v for k, v in options.items()}}
        else:
            q = {"type": "score", "instructions": question_text, "criteria": options}

        t = time.perf_counter()
        try:
            r = engine.decide_one(state, q)
        except JPTError as e:
            print(f"error: {e}\n")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"error: {type(e).__name__}: {e}\n")
            continue
        ms = (time.perf_counter() - t) * 1000

        if r["type"] == "noul":
            print(f"\n  P(true)   : {r['noul']:.3f}   confidence {r['confidence']:.3f}")
        elif r["type"] == "score":
            print(f"\n  score     : {r['score']:.2f}   confidence {r['confidence']:.3f}")
        else:
            print(f"\n  answer    : {r['choice']}   confidence {r['confidence']:.3f}")
        for name, p in sorted(r["probabilities"].items(), key=lambda kv: -kv[1]):
            print(f"    {str(name):<24} {p:6.3f}  " + "#" * int(round(p * 30)))
        print(f"  {ms:.0f} ms\n")


if __name__ == "__main__":
    main()