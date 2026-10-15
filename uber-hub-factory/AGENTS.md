# AGENTS.md — uber-hub-factory

Automated ICM pipeline for consolidating scattered agent skills into a unified, late-binding Uber API Hub.

## Where Everything Lives
- `01_inventory/`: Discovers source skills, scripts, rubrics, and external callers.
- `02_scaffold_hub/`: Copies template, registers suites, renames nested `SKILL.md` to `rubric.md`.
- `03_shims_and_compat/`: Generates backward-compatible shell wrappers for `~/.local/bin/`.
- `04_verify_and_sync/`: Runs health checks, deletes obsolete standalone folders, and syncs via `sync-skills --push`.
- `_templates/uber-hub/`: Reusable canonical Uber API hub starter files.
- `scripts/`: Pipeline driver (`factory.py`) and automated verification tests.

## Routing
| Intent / Task | Go To |
|---|---|
| Consolidate skills into a new or existing hub | `python3 scripts/factory.py build --hub <name> --skills <s1,s2>` |
| Inspect existing hub structure | `python3 scripts/factory.py inspect --hub <name>` |
| Test hub template integrity | `python3 scripts/test_factory.py` |

## Not This Workspace
- Modifying skill runtime code logic: Edit the skill directly or in target hub.
- Local inference port configuration: Handled in `local-hub` and `/run/media/rodri/AI/AGENTS.md`.
- Code review kitchens and standards: Handled in `review-hub`.

## Status Rules
- `COMPLETE`: Output exists in stage folder and is newer than upstream inputs.
- `STALE`: Upstream source skill was edited after stage output was generated.
- `RESET`: Clear `output/` directories and rerun from `01_inventory`.
