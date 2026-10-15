# uber-hub-factory

Non-destructive ICM pipeline and CLI factory that unifies native standalone skills into late-binding Uber API Hubs.

## Purpose
Provides unified discovery and execution across multiple related skills without the friction of deleting or moving source directories. Preserves standalone skills, native `SKILL.md` files, and existing CLIs while enabling late-binding search, list, inspect, and response projection.

## 3-Stage ICM Pipeline
1. **`01_discover/`**: Scans candidate skills, scripts, and callers; outputs `manifest.json`.
2. **`02_bridge/`**: Generates non-destructive router `<hub>.py`, `SKILL.md`, `README.md`, and links `~/.local/bin/<hub>`.
3. **`03_verify/`**: Runs Grounded Verification tests proving hub commands and ensuring standalone skills remain intact.

## Quickstart
```bash
# Bridge standalone skills into a unified hub
uber-hub-factory bridge --hub academic-icm --skills canvas-cli,zoom-recorder,cornell-notes

# Run discovery only
uber-hub-factory discover --skills canvas-cli,zoom-recorder,cornell-notes

# Run verification only
uber-hub-factory verify --hub academic-icm
```
