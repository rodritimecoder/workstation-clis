# Stage 01: Discover & Map

## Purpose
Inspect candidate standalone skills in `/run/media/rodri/AI/skills/`, extract their metadata, CLI entrypoints, and contracts without altering any source files.

## Input
- Comma-separated list of standalone skill directory names (e.g. `canvas-cli,zoom-recorder,cornell-notes`).
- Existing `SKILL.md` and `scripts/` directories inside each candidate skill.

## Process
1. Locate each skill folder in `/run/media/rodri/AI/skills/<skill-name>`.
2. Parse `SKILL.md` frontmatter (name, description, tags).
3. Discover executable entrypoints in `scripts/`, root `<skill-name>.py`, or binaries.
4. Extract CLI subcommands and capabilities.
5. Identify external callers and documentation references.
6. Assemble into structured discovery manifest.

## Output
- `output/manifest.json`: Machine-readable mapping of discovered skills, entrypoints, and descriptions.

## Human / Agent Check
- Verify that every listed skill directory was found and resolved.
- Verify entrypoint paths point to real executable files.
- Confirm source skills remain untouched in their canonical locations.
