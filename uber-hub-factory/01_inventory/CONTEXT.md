# 01_inventory — Skill Discovery & Callers Mapping

## Purpose
Inspect the candidate skill folders to be swallowed, index their executable scripts and rubrics, and map all external callers on the workstation so that no existing scripts break.

## Inputs
- Candidate skill directory paths in `/run/media/rodri/AI/skills/`.

## Process
1. Read each candidate's `SKILL.md` (frontmatter: name, description).
2. Enumerate executable scripts in `scripts/`.
3. Search for external referrers across the machine (`git grep` or `grep -rn` in skills repo).
4. Emit structured JSON inventory to `output/manifest.json`.

## Outputs
- `output/manifest.json`: Full manifest of source skills, entrypoints, and callers.

## Human / Agent Check
- Verify that every candidate skill was located and its primary entrypoint identified.
