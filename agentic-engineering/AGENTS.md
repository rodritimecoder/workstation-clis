# AGENTS.md — agentic-engineering

Autonomous production pipeline implementing Kem's (Glitch Cat Club) 7-step loop.

## Where Everything Lives
- `scripts/kanban.py`: Target-local file-based Kanban board engine (`.kanban/`).
- `scripts/listener.py`: Event listener monitoring and auto-claiming inbound cards.
- `scripts/judge.py`: Fresh-context unbiased evaluator applying Kem's rejection delta (`SENT BACK`).
- `scripts/splitter.py`: Multi-model sandbox allocator and task partitioner.
- `_templates/`: Kanban directory template and canonical task card template.
- `agentic.py`: Unified CLI entrypoint.

## Routing
| Intent / Task | Go To |
|---|---|
| Initialize Kanban in a project | `agentic init [path]` |
| Add or move cards on board | `agentic kanban add <title>` / `agentic kanban list` |
| Run event listener | `agentic listen [--once]` |
| Run unbiased judge evaluation | `agentic judge <card-id> [--model flash]` |
| Split task into parallel lanes | `agentic split <title>` |
| Run full 7-step loop | `agentic run <card-id>` |
| Run test suite | `python3 scripts/test_agentic.py` |

## Not This Workspace
- Individual code changes: Performed in target project workspaces or worktrees.
- Local inference port management: Handled in `local-hub` (:8080, :8083, :8085).
- Code review rubrics: Handled in `review-hub`.

## Status Rules
- `COMPLETE`: Card is in `04_done/` with all criteria checked and Judge stamp.
- `REJECTED`: Judge fired pink arrow; card returned to `02_picked_up/` with delta.
- `STALE`: Upstream task brief was modified after card was created.
