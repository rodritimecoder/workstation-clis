# AGENTS.md — uber-hub-factory

Non-destructive ICM pipeline and CLI factory that bridges native standalone skills into unified, late-binding Uber API Hubs.

## Where Everything Lives
- `01_discover/`: Scans standalone skills, CLI entrypoints, and callers without altering source files.
- `02_bridge/`: Generates router `<hub>.py`, `SKILL.md`, and `README.md` using dynamic sibling resolution.
- `03_verify/`: Grounded verification proving hub commands and verifying standalone skills remain intact.
- `_templates/uber-hub/`: Canonical templates for non-destructive router and documentation.
- `scripts/`: Driver script (`factory.py`) and verification tests (`test_factory.py`).

## Routing
| Intent / Task | Go To |
|---|---|
| Bridge skills into a new or existing hub | `python3 uber_hub_factory.py bridge --hub <name> --skills <s1,s2>` |
| Scan standalone skills and generate manifest | `python3 uber_hub_factory.py discover --skills <s1,s2>` |
| Run grounded verification on a hub | `python3 uber_hub_factory.py verify --hub <name>` |
| Run test suite | `python3 scripts/test_factory.py` |

## Not This Workspace
- Modifying individual skill logic: Edit the standalone skill directly.
- Local inference endpoints: Handled in `local-hub` and `/run/media/rodri/AI/AGENTS.md`.
- Code review suites: Handled in `review-hub`.

## Status Rules
- `COMPLETE`: Output exists in stage folder and is newer than upstream inputs.
- `STALE`: Upstream source skill was edited after stage output was generated.
- `RESET`: Clear `output/` directories and rerun from `01_discover`.
