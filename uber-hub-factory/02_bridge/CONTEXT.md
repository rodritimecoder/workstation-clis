# Stage 02: Bridge & Scaffold

## Purpose
Generate the non-destructive router hub and late-binding dispatch interface connecting native standalone skills.

## Input
- `01_discover/output/manifest.json`.
- Hub name, description, and templates (`_templates/uber-hub/`).

## Process
1. Initialize the hub directory in `/run/media/rodri/AI/skills/<hub-name>/`.
2. Generate `<hub-name>.py` router using sibling-resolution lookup (`HUB_DIR.parent / <suite>`).
3. Generate hub `SKILL.md` with concise metadata and late-binding routing table.
4. Generate hub `README.md`.
5. Link executable binary to `~/.local/bin/<hub-name>`.
6. Ensure standalone skill executables in `~/.local/bin/` remain intact and callable.

## Output
- `output/bridge_summary.json`: Record of generated files, router paths, and symlinks.
- `/run/media/rodri/AI/skills/<hub-name>/<hub-name>.py`
- `/run/media/rodri/AI/skills/<hub-name>/SKILL.md`
- `/run/media/rodri/AI/skills/<hub-name>/README.md`
- `~/.local/bin/<hub-name>`

## Human / Agent Check
- Check that no source skill folders were moved or deleted.
- Check that source `SKILL.md` files were NOT renamed or overwritten.
- Verify `<hub-name>.py` compiles and has executable permissions (`chmod +x`).
