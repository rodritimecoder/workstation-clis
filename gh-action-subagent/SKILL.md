---
name: gh-action-subagent

description: >
  Spawn isolated cloud subagents inside GitHub Actions VMs with full Linux shell,
  Git, and headless Chrome CDP browser skills. Use when delegating parallel coding tasks,
  running browser E2E checks in a sandbox, or fixing issues asynchronously via Pull Requests.

compatibility: "Requires network access to GitHub Actions, an authenticated GitHub CLI or GITHUB_TOKEN, and an OpenCode Go token in the repository secrets."
allowed-tools: "Bash(gh:*) Bash(python3:*) Read Write"
---

# GitHub Actions Cloud Subagent Skill

Use this skill to dispatch tasks to ephemeral GitHub Actions runners via a single API call. Each subagent runs in an isolated Ubuntu VM with the `playwright` skill's native client (browser daemon on :9222), the guard hooks, and the OpenCode Go tool loop in `scripts/go_agent.py`.

## Prerequisites
- GitHub CLI (`gh`) authenticated, OR `GITHUB_TOKEN` exported in the environment.
- Workflow file `.github/workflows/subagent.yml` committed to the repository `main` branch — copy `assets/subagent.yml` from this skill; its `workflow_dispatch` inputs (`task`, `target_branch`, `model`) are exactly what `gh-subagent dispatch` sends.
- Repository secret `OPENCODE_GO_TOKEN` added in GitHub repo settings. The token is the OpenCode Go credential; the workflow refuses to start without it, before it creates a branch.

### Which models this runner can drive

The Go catalog serves three shapes, and `go_agent.py` speaks one: **OpenAI `chat/completions`**. Claude Haiku, Qwen and MiniMax M3 use the Anthropic shape; Grok and the GPT Luna pair use the Responses shape. The runner refuses those ids up front with a suggestion rather than failing mid-task on `ModelProtocolUnsupported`.

Observed in use (2026-10-25, 9 dispatches): `deepseek-v4-pro` completed both multi-file edits it was given. `glm-5.3` twice answered in prose instead of calling a tool, even with `tool_choice: required` — the runner asks once more, then fails. Treat that as a model behaviour, not a harness bug: prefer the DeepSeek lanes for write-heavy runs.

Safe choices: `deepseek-v4.1-flash`, `deepseek-v4-pro`, `glm-5.3-flash`, `glm-5.3`, `kimi-k3`, `kimi-k3.1-pro`, `mimo-v2.6-*`, `longcat-2.0`.

### Which model, now that it has been measured

The catalog has 30 ids; eight were actually driven today. Cost is from the Go
console, outcome is whether the lane produced its files.

| Job | Model | Evidence |
| :--- | :--- | :--- |
| **Tool loop, lanes, multi-file edits** | `deepseek-v4.1-flash` | 10/10 lanes completed; $1.09 for 822 requests (~$0.0013 each); 34,670 req/5h, $80 pool |
| **One-shot judgement** (read a diff, score an audit) | `deepseek-v4-pro` | the only pro that finished a multi-file edit; $0.0041/request; 1,050 req/5h, $15 pool |
| **Not usable in this loop** | `kimi-k3`, `kimi-k3.1-pro`, `glm-5.3`, `mimo-*`, `minimax-m3.1-flash` | answered in prose instead of calling a tool, twice each; `tool_choice: required` did not change it |
| **Wrong protocol** | `claude-haiku-5-5`, `qwen3.8-*`, `qwen3.7-plus`, `minimax-m3`, `grok-4.7`, `gpt-*-luna`, `muse-*` | anthropic / responses shapes; the runner refuses them at startup |

Sizing and drift live in one script, which is also the only thing that knows the
whole catalog:

```bash
go-roster --check                 # is the plan connected, and does the roster match it
go-roster --verify                # exit 1 if a curated id is no longer served
go-roster --plan "deepseek-v4.1-flash:6,deepseek-v4-pro:2"
go-roster --tier 2 --json
```

## Commands

### 1. Dispatch a New Cloud Subagent
```bash
gh-subagent dispatch \
  --task "Start dev server, use CDP skill to inspect /login, fix the layout bug, and open a PR" \
  --branch "agent/fix-login" \
  --model "deepseek-v4.1-flash"
```

### 2. List Active / Recent Cloud Subagents
```bash
gh-subagent status
```

### 3. Fetch Logs / Output of a Subagent Run
```bash
gh-subagent logs <run_id>
```

## Parallel Delegation Pattern
You can dispatch up to 5 subagents concurrently:
1. Dispatch each independent subtask on its own `--branch` (`agent/task-1`, `agent/task-2`).
2. Poll status with `subagent_ctl.sh status`.
3. Inspect the created Pull Requests or workflow artifacts (screenshots and logs) once completed.
