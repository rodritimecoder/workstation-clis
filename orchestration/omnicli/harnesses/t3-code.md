# 🛠️ T3 Code Harness Guide for omnicli

> *"T3 Code is an agentic IDE powered by the Agent Client Protocol (ACP) and host-managed MCP tools."*

This guide specifies how `omnicli` integrates natively with **T3 Code** as a first-party tool discovery, execution, and local-inference gateway.

---

## ⚡ Integration Faces in T3 Code

T3 Code agents interact with `omnicli` through two primary faces:

### Face A: MCP Server (JSON-RPC 2.0 over stdio)

`omnicli mcp` runs a standard MCP server exposing four high-leverage meta-tools:

| Tool | Purpose | Advantage in T3 Code |
| :--- | :--- | :--- |
| `omni_discover` | Natural-language intent search over BM25 catalog | Returns compact JSON (~300 bytes) instead of 150k tokens of prompts |
| `omni_describe` | Retrieve usage contract for exactly ONE tool | Progressive disclosure; loads schema on demand |
| `omni_invoke` | Run any tool with strict byte caps & JSON projections | Bounded output prevents context window exhaustion |
| `omni_status` | Health probe for ports (:8080-:8087) and catalog | Instant status check without terminal commands |

#### MCP Registration Configuration

To register `omnicli` as an MCP server in T3 Code:

```json
{
  "mcpServers": {
    "omnicli": {
      "command": "omnicli",
      "args": ["mcp"]
    }
  }
}
```

### Face B: Direct Terminal / Bash Invocation

When executing terminal commands in T3 Code (`run_command`), use `omnicli` to guard against context flooding:

```bash
# 1. Search for a tool by natural intent
omnicli search "transcribe zoom lecture"

# 2. Inspect its contract
omnicli describe zoom-recorder/scripts/zoom_download

# 3. Run it with output capping and projection
omnicli invoke zoom-recorder/scripts/zoom_download \
  --omni-max-bytes 8000 \
  --omni-project "status,transcript_path" \
  -- --url "https://zoom.us/rec/..."
```

---

## 🐍 Code Mode in T3 Code (`omnicli exec`)

Instead of making 10 round-trip tool calls across turns, write one Python plan script that executes in a single turn:

```bash
omnicli exec plan.py --sandbox write
```

```python
# plan.py
from omnicli_tools import search, invoke, zoom

# 1. Discover tools inside the plan
hits = search("audio transcription", limit=3)

# 2. Invoke tool with typed bindings
result = zoom(url="https://zoom.us/rec/share/abc", format="md")

# 3. Print only the synthesis back to T3 Code
print(f"Downloaded and transcribed: {result['output'][:300]}")
```

Intermediates stay on disk or in Python memory; only the final print lands in T3 Code's context window.

---

## 🖼️ Visual Presentation & Previews

T3 Code provides `html_preview` and `html_render` tools. When `omnicli` produces tabular, diagnostic, or graphical reports:
1. Output HTML report (e.g. `omnicli status --json` rendered to an HTML dashboard).
2. Pass the HTML file path to `html_preview`, then `html_render`.
3. Never start background HTTP servers to display static results.

---

## 🏛️ T3 Code Host Invariants

1. **Reactive Wakeups (Zero Polling):** Never use `sleep` or poll tasks in a loop. When launching background commands, let T3 Code resume execution automatically.
2. **Delegate Worktrees:** Never manually run `git worktree add` for child delegates in shell. Pass `isolation: "worktree"` in `delegate_task`.
3. **Artifact Directory:** Store run traces, buffers, and intermediate step outputs in `<appDataDir>/brain/<conversation-id>/scratch/` or `.omnicli/`.
4. **Verbatim Thread Links:** Always use the markdown `link` verbatim when referencing threads.

---

## 🔍 Verification

Run the automated verification suite to confirm T3 Code readiness:

```bash
omnicli harness verify t3-code
```
