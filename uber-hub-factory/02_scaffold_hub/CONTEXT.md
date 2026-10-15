# 02_scaffold_hub — Hub Construction & Rubric Inlining

## Purpose
Deploy the unified Uber API runner, copy scripts and rubrics into `suites/`, and rename all nested `SKILL.md` files to `rubric.md` to prevent agent harness registration bloat.

## Inputs
- `01_inventory/output/manifest.json`
- `_templates/uber-hub/`

## Process
1. Create target hub directory `/run/media/rodri/AI/skills/<hub-name>/`.
2. Instantiate `hub.py`, `SKILL.md`, and `README.md` from templates, populating the `SUITES` dictionary.
3. Copy each skill's assets into `suites/<skill_name>/`.
4. Rename `suites/<skill_name>/SKILL.md` to `rubric.md`.
5. Ensure `suites/<skill_name>/` has NO residual `SKILL.md` files.

## Outputs
- `/run/media/rodri/AI/skills/<hub-name>/` (complete unified hub).
- `output/scaffold_report.json`

## Human / Agent Check
- Run `find /run/media/rodri/AI/skills/<hub-name>/suites/ -name "SKILL.md"` to confirm ZERO internal registration bloat.
