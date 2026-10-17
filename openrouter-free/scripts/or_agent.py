#!/usr/bin/env python3
"""
or_agent.py — Consolidated OpenRouter Free Multimodal & Subagent Runner
Implements the Uber OmniMCP / aifx "Code Mode" protocol:
  - Validated OpenRouter Free slugs (Nemotron Ultra, Nemotron Lightning, Mercury Decide, Fish TTS, LFM Embed)
  - Compound batch script execution (run_bash_batch) with directory state and error persistence
  - Response projection & disk buffering (--out, --project) to keep LLM context lean
  - 4-Tier failover: Local Homelab -> Free High-Reasoning -> Dynamic Free -> Gemini
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_fallbacks():
    candidates = [
        Path.home() / ".agent_keys.env",
        Path.home() / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in candidates:
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


_load_env_fallbacks()

# --- VALIDATED MODEL SLUGS ---

CHAT_CASCADE = [
    {
        "provider": "homelab",
        "model": "agent-coder",
        "url": os.environ.get("HOMELAB_LITELLM_URL", "").rstrip("/") + "/chat/completions",
        "env_key": "HOMELAB_LITELLM_KEY",
    },
    {
        "provider": "openrouter",
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "openrouter",
        "model": "dots-studio/dots-3-note-preview:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "openrouter",
        "model": "thinkingmachines/inkling:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "openrouter",
        "model": "nvidia/nemotron-3.5-lightning:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "openrouter",
        "model": "qwen/qwen-2.5-coder-32b-instruct:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "openrouter",
        "model": "openrouter/free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "env_key": "GEMINI_API_KEY",
    },
    {
        "provider": "gemini",
        "model": "gemini-flash-lite-latest",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "env_key": "GEMINI_API_KEY",
    },
    {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "env_key": "GEMINI_API_KEY",
    },
]

DECIDE_CASCADE = [
    "inception/mercury-decide:free",
    "nvidia/nemotron-3.5-lightning:free",
    "openrouter/free",
]

EMBED_CASCADE = [
    "liquid/lfm-2.5-embedding-350m:free",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
]

RERANK_CASCADE = [
    "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
]

TTS_CASCADE = [
    "fish-audio/s2.1-pro-free:free",
]

# --- BATCHED TOOL SCHEMA ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash_batch",
            "description": (
                "Execute an ordered sequence of shell commands inside a single compound bash environment. "
                "Commands share working directory (e.g. `cd dir` affects subsequent commands). "
                "CRITICAL: Always batch reconnaissance, file inspection, edits, and test runs together "
                "in the `commands` array to minimize API turn consumption."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of shell commands to execute sequentially.",
                    }
                },
                "required": ["commands"],
            },
        },
    }
]


def _http_post_json(url: str, payload: dict, api_key: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/RooVetGit/Roo-Cline",
            "X-Title": "Roo Code",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_llm_with_cascade(messages: list, preferred_model: str = None, enable_tools: bool = False):
    cascade = [c for c in CHAT_CASCADE if c["url"] != "/chat/completions"]
    if preferred_model:
        if "gemini" in preferred_model.lower():
            cascade.insert(
                0,
                {
                    "provider": "gemini",
                    "model": preferred_model,
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    "env_key": "GEMINI_API_KEY",
                },
            )
        else:
            cascade.insert(
                0,
                {
                    "provider": "openrouter",
                    "model": preferred_model,
                    "url": "https://openrouter.ai/api/v1/chat/completions",
                    "env_key": "OPENROUTER_API_KEY",
                },
            )

    last_err = None
    for target in cascade:
        api_key = os.environ.get(target["env_key"], "")
        if not api_key:
            continue

        payload = {
            "model": target["model"],
            "messages": messages,
        }
        if enable_tools:
            payload["tools"] = TOOLS
            payload["parallel_tool_calls"] = True

        if target["provider"] == "openrouter":
            payload["provider"] = {
                "require_parameters": True,
                "allow_fallbacks": True,
            }

        try:
            timeout_s = 5 if target["provider"] == "homelab" else 90
            data = _http_post_json(target["url"], payload, api_key, timeout=timeout_s)
            choice = data["choices"][0]["message"]
            if not choice.get("content") and choice.get("reasoning"):
                choice["content"] = choice["reasoning"]
            return choice, target["model"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            sys.stderr.write(f"[openrouter-free] {target['model']} HTTP {e.code}: {err_body[:200]}\n")
            last_err = f"HTTP {e.code}: {err_body[:100]}"
            if e.code in (429, 503):
                time.sleep(2)
                continue
        except Exception as e:
            sys.stderr.write(f"[openrouter-free] {target['model']} error: {e}\n")
            last_err = str(e)

    raise RuntimeError(f"All cascade endpoints exhausted. Last error: {last_err}")


def execute_compound_batch(commands: list, cwd: str = None, timeout_total: int = 180) -> str:
    """
    Executes a list of commands in a single bash script.
    Maintains environment and working directory across commands while stopping early on failure.
    """
    if isinstance(commands, str):
        commands = [commands]

    # Build compound script that prints markers and runs with set -e
    script_lines = [
        "#!/usr/bin/env bash",
        "set -eo pipefail",
    ]
    for idx, cmd in enumerate(commands):
        escaped_cmd = cmd.replace("'", "'\\''")
        script_lines.append(f"echo '--- [STEP {idx + 1}/{len(commands)}] $ {escaped_cmd} ---'")
        script_lines.append(cmd)

    full_script = "\n".join(script_lines)

    try:
        proc = subprocess.run(
            ["bash", "-c", full_script],
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=timeout_total,
        )
        combined = (proc.stdout + "\n" + proc.stderr).strip()
        exit_msg = f"\n[Batch Finished with exit code {proc.returncode}]"
        return (combined + exit_msg)[:12000]
    except subprocess.TimeoutExpired as te:
        stdout = te.stdout.decode("utf-8", errors="ignore") if isinstance(te.stdout, bytes) else (te.stdout or "")
        return f"{stdout}\n[ERROR: Batch timed out after {timeout_total}s]"
    except Exception as ex:
        return f"[ERROR: Execution failure: {ex}]"


def run_agent_loop(prompt: str, preferred_model: str = None, max_turns: int = 12, out_file: str = None):
    system_prompt = (
        "You are an autonomous coding and system verification subagent.\n"
        "You have bash access via `run_bash_batch`.\n"
        "CRITICAL: Always batch multiple commands into single turns to conserve rate limits.\n"
        "Commands in the array share directory context and stop on fatal errors.\n"
        "Inspect files, make minimal necessary edits, verify with tests, and output a concise report.\n\n"
        "Available Workstation & Browser Verification CLIs in PATH:\n"
        "- `fast-cdp verify <url> [--assert-selector <sel>] [--assert-text <txt>] [--screenshot <path>] [--json]`: Sub-second native Chrome DevTools Protocol verification on port :9222.\n"
        "- `fast-cdp snap <url>`: Instant viewport accessibility text snapshot.\n"
        "- `ocr read <file>`: LightOnOCR-3-1B document and image OCR.\n"
        "- `jev bool / choice / score`: Calibrated non-generative decisions.\n"
        "- `audiocpp tts / asr`: Speech synthesis and verbatim transcription.\n"
        "- `local-hub search <intent>` / `local-hub run <skill>`: Discover and run any workstation skill.\n"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    used_model = preferred_model or "auto"
    final_content = ""

    for turn in range(1, max_turns + 1):
        sys.stderr.write(f"\n[Turn {turn}/{max_turns}] Invoking model cascade...\n")
        msg, used_model = call_llm_with_cascade(messages, preferred_model=preferred_model, enable_tools=True)
        messages.append(msg)

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            final_content = msg.get("content", "")
            print(f"\n--- Subagent Completed via {used_model} in {turn} turn(s) ---")
            print(final_content)
            if out_file:
                Path(out_file).write_text(final_content, encoding="utf-8")
            return final_content

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name")
            raw_args = tc.get("function", {}).get("arguments", "{}")
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

            if fn_name == "run_bash_batch":
                cmds = args.get("commands", [])
                sys.stderr.write(f"  [Turn {turn} | {used_model}] Executing batch of {len(cmds)} command(s)...\n")
                output = execute_compound_batch(cmds)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn_name,
                        "content": output,
                    }
                )

    sys.stderr.write(f"\n[openrouter-free] Subagent finished all {max_turns} turns.\n")
    return final_content or (messages[-1].get("content") if messages else "")



def run_single_chat(prompt: str, preferred_model: str = None, out_file: str = None):
    messages = [{"role": "user", "content": prompt}]
    msg, used_model = call_llm_with_cascade(messages, preferred_model=preferred_model, enable_tools=False)
    content = msg.get("content", "")
    res = {"model": used_model, "content": content}
    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
    return res


def run_decide(query: str, options: list = None, preferred_model: str = None):
    """Calibrated probability / discrete triage using OpenRouter decisions API or LLM cascade."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for decide mode.")

    model = preferred_model or DECIDE_CASCADE[0]

    # Native OpenRouter decisions API for inception/mercury-decide
    if "inception" in model or "decide" in model:
        try:
            if options:
                criteria = {opt: f"The option '{opt}' applies to: {query}" for opt in options}
                questions = {
                    "decision": {
                        "type": "choice",
                        "instructions": query,
                        "criteria": criteria,
                    }
                }
            else:
                questions = {
                    "decision": {
                        "type": "noul",
                        "instructions": query,
                    }
                }

            dec_payload = {
                "model": model,
                "state": query,
                "questions": questions,
            }
            res = _http_post_json("https://openrouter.ai/api/alpha/decisions", dec_payload, api_key, timeout=45)
            ans = res.get("answers", {}).get("decision", {})
            return {
                "model": res.get("model", model),
                "verdict": ans.get("choice") or ans.get("verdict") or ans.get("decision"),
                "probabilities": ans.get("probabilities", {}),
                "confidence": ans.get("confidence"),
                "raw": ans,
            }
        except Exception as e:
            # Fall back to next model in cascade
            pass

    # Fallback to chat completions with prompt-based triage
    prompt_text = query
    if options:
        opts_formatted = "\n".join(f"- {o}" for o in options)
        prompt_text = f"{query}\n\nSelect strictly one of these options:\n{opts_formatted}"

    payload = {
        "model": "nvidia/nemotron-3.5-lightning:free",
        "messages": [
            {"role": "system", "content": "You are a calibrated zero-shot decision router. Give your verdict with confidence score."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.0,
    }
    data = _http_post_json("https://openrouter.ai/api/v1/chat/completions", payload, api_key, timeout=45)
    content = data["choices"][0]["message"].get("content", "")
    return {"model": "nvidia/nemotron-3.5-lightning:free", "verdict": content.strip()}



def run_batched_embeddings(inputs: list, preferred_model: str = None, out_json: str = None):
    """Embeds an array of texts or file contents in 1 single HTTP request."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for embeddings.")

    resolved_texts = []
    for item in inputs:
        p = Path(item)
        if p.is_file():
            resolved_texts.append(p.read_text(errors="ignore")[:8000])
        else:
            resolved_texts.append(item)

    models = ([preferred_model] if preferred_model else []) + [m for m in EMBED_CASCADE if m != preferred_model]
    last_err = None
    for model in models:
        payload = {
            "model": model,
            "input": resolved_texts,
            "provider": {"allow_fallbacks": True},
        }
        try:
            data = _http_post_json("https://openrouter.ai/api/v1/embeddings", payload, api_key, timeout=60)
            vectors = [
                {
                    "index": idx,
                    "source": inputs[idx],
                    "dimensions": len(row["embedding"]),
                    "embedding": row["embedding"],
                }
                for idx, row in enumerate(data.get("data", []))
            ]
            result = {"model": model, "count": len(vectors), "results": vectors}
            if out_json:
                Path(out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
            return {
                "model": model,
                "count": len(vectors),
                "dimensions": vectors[0]["dimensions"] if vectors else 0,
                "saved_to": out_json,
                "preview_dims": vectors[0]["embedding"][:5] if vectors else [],
            }
        except Exception as e:
            sys.stderr.write(f"[openrouter-free embed] {model} error: {e}\n")
            last_err = e

    raise RuntimeError(f"All free embedding endpoints failed: {last_err}")


def run_tts(text: str, out_path: str = "output.mp3", preferred_model: str = None):
    """Generates speech audio using free OpenRouter endpoints (fish-audio/s2.1-pro-free:free)."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for TTS.")

    models = ([preferred_model] if preferred_model else []) + [m for m in TTS_CASCADE if m != preferred_model]
    last_err = None
    for model in models:
        # Try native audio/speech endpoint first
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/audio/speech",
                data=json.dumps({"model": model, "input": text, "voice": "alloy"}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/local-agent-harness",
                    "X-Title": "openrouter-free-skill",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw_bytes = resp.read()
                Path(out_path).write_bytes(raw_bytes)
                return {"model": model, "status": "saved", "out_path": out_path, "bytes": len(raw_bytes)}
        except Exception as e:
            # Fallback to chat completions audio modality
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": text}],
                    "modalities": ["text", "audio"],
                    "audio": {"voice": "alloy", "format": "mp3"},
                }
                data = _http_post_json("https://openrouter.ai/api/v1/chat/completions", payload, api_key, timeout=60)
                msg = data["choices"][0]["message"]
                audio_b64 = msg.get("audio", {}).get("data")
                if audio_b64:
                    Path(out_path).write_bytes(base64.b64decode(audio_b64))
                    return {"model": model, "status": "saved", "out_path": out_path}
            except Exception as e2:
                sys.stderr.write(f"[openrouter-free tts] {model} error: {e2}\n")
                last_err = e2

    raise RuntimeError(f"All free TTS endpoints failed: {last_err}")


def run_multi_pipeline(chat_prompt: str = None, embed_inputs: list = None, tts_text: str = None, tts_out: str = "output.mp3", model: str = None):
    """Sequential pipeline to prevent 429 concurrency throttling while writing artifacts cleanly to disk."""
    summary = {}
    if chat_prompt:
        try:
            summary["chat"] = run_single_chat(chat_prompt, preferred_model=model)
        except Exception as e:
            summary["chat"] = {"error": str(e)}

    if embed_inputs:
        try:
            summary["embed"] = run_batched_embeddings(embed_inputs)
        except Exception as e:
            summary["embed"] = {"error": str(e)}

    if tts_text:
        try:
            summary["tts"] = run_tts(tts_text, out_path=tts_out)
        except Exception as e:
            summary["tts"] = {"error": str(e)}

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenRouter Free Multimodal & Subagent CLI (Uber Protocol)")
    sub = parser.add_subparsers(dest="mode", required=True)

    # 1. Agent Mode
    p_agent = sub.add_parser("agent", help="Run autonomous subagent loop with compound bash batching")
    p_agent.add_argument("--prompt", required=True, help="Task instructions")
    p_agent.add_argument("--model", default=None, help="Specific model override")
    p_agent.add_argument("--max-turns", type=int, default=12, help="Maximum conversation turns")
    p_agent.add_argument("--out", default=None, help="Save final subagent report to file")

    # 2. Chat Mode
    p_chat = sub.add_parser("chat", help="Single-turn completion or code review")
    p_chat.add_argument("--prompt", required=True, help="Prompt text or diff")
    p_chat.add_argument("--model", default=None, help="Specific model override")
    p_chat.add_argument("--out", default=None, help="Save output to file")

    # 3. Decide Mode
    p_decide = sub.add_parser("decide", help="Calibrated decision routing (Mercury Decide)")
    p_decide.add_argument("--query", required=True, help="Question or routing prompt")
    p_decide.add_argument("--options", nargs="*", default=None, help="List of candidate options")
    p_decide.add_argument("--model", default=None, help="Specific model override")

    # 4. Embed Mode
    p_embed = sub.add_parser("embed", help="Batched embeddings (LFM / Nemotron Embed)")
    p_embed.add_argument("--inputs", nargs="+", required=True, help="Texts or file paths")
    p_embed.add_argument("--model", default=None, help="Specific model override")
    p_embed.add_argument("--out-json", default=None, help="Save full embedding vectors to JSON file")

    # 5. TTS Mode
    p_tts = sub.add_parser("tts", help="Generate speech audio (Fish Audio Free)")
    p_tts.add_argument("--text", required=True, help="Text to speak")
    p_tts.add_argument("--out", default="output.mp3", help="Output MP3 path")
    p_tts.add_argument("--model", default=None, help="Specific model override")

    # 6. Multi Pipeline
    p_multi = sub.add_parser("multi", help="Execute multi-modal pipeline without concurrency lock")
    p_multi.add_argument("--chat", default=None, help="Prompt for chat")
    p_multi.add_argument("--embed", nargs="*", default=None, help="Inputs to embed")
    p_multi.add_argument("--tts", default=None, help="Text to speak")
    p_multi.add_argument("--tts-out", default="output.mp3", help="Output audio file")
    p_multi.add_argument("--model", default=None, help="Chat model override")

    args = parser.parse_args()

    if args.mode == "agent":
        run_agent_loop(args.prompt, args.model, args.max_turns, args.out)
    elif args.mode == "chat":
        print(json.dumps(run_single_chat(args.prompt, args.model, args.out), indent=2))
    elif args.mode == "decide":
        print(json.dumps(run_decide(args.query, args.options, args.model), indent=2))
    elif args.mode == "embed":
        print(json.dumps(run_batched_embeddings(args.inputs, args.model, args.out_json), indent=2))
    elif args.mode == "tts":
        print(json.dumps(run_tts(args.text, args.out, args.model), indent=2))
    elif args.mode == "multi":
        print(json.dumps(run_multi_pipeline(args.chat, args.embed, args.tts, args.tts_out, args.model), indent=2))
