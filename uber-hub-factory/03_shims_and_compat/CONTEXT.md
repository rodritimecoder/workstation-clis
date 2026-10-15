# 03_shims_and_compat — Backward Compatibility Shimming

## Purpose
Generate executable shell shims in `~/.local/bin/` so that any legacy script or prompt calling the old CLI name transparently routes through `<hub-name> run <suite> "$@"`.

## Inputs
- `01_inventory/output/manifest.json`

## Process
1. For each original skill CLI name:
   - Check if an existing binary/symlink exists in `~/.local/bin/`.
   - Replace with an executable bash shim:
     ```bash
     #!/usr/bin/env bash
     exec <hub-name> run <suite> "$@"
     ```
2. Create main hub binary link:
   - `~/.local/bin/<hub-name>` -> `/run/media/rodri/AI/skills/<hub-name>/<hub-name>.py`

## Outputs
- Updated `~/.local/bin/` wrappers.
- `output/shims_report.json`

## Human / Agent Check
- Test running `<legacy-cli> --help` to confirm it routes through the new hub without breaking.
