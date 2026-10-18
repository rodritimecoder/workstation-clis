# 02_plan_split — Plan Approval & Task Splitter

One job: Break feature spec into vertical slices and create holdout tests.

## Inputs
- Working: ../01_inbox/output/feature_spec.md
- Reference: ../_shared/rules.md

## Process
1. Decompose into independent vertical slices (frontend, backend, schema).
2. Write holdout verification tests into `../07_holdouts/`.
3. Create task cards in `../03_kanban/todo/`.
4. Emit `output/execution_plan.md`.

## Outputs
- `output/execution_plan.md`
- Task cards in `../03_kanban/todo/`

## Human check
Human approves plan (the 'Why and Why Not') before builders spawn.
