# uber-hub-factory

Automated ICM Pipeline & CLI Factory for Consolidating Agent Skills into Unified Uber API Hubs.

## Purpose
Eliminates context window bloat and maintenance drift by consolidating scattered individual skills into unified, late-binding hubs (like `local-hub` and `review-hub`).

## Pipeline Architecture
1. **`01_inventory/`**: Scans candidate skills, scripts, and machine-wide referrers.
2. **`02_scaffold_hub/`**: Deploys canonical Uber API runner, inlines rubrics into `suites/`, and renames nested `SKILL.md` to `rubric.md`.
3. **`03_shims_and_compat/`**: Generates transparent bash shims in `~/.local/bin/` so old CLI commands continue working.
4. **`04_verify_and_sync/`**: Runs Grounded Verification, purges obsolete standalone folders, and syncs via `sync-skills --push`.

## Quickstart
```bash
# Consolidate candidate skills into a new hub
uber-hub-factory build --hub academic-hub --skills canvas-cli,zoom-recorder,cornell-notes,markitdown-cli

# Run inventory pass only
uber-hub-factory inventory --skills canvas-cli,zoom-recorder
```
