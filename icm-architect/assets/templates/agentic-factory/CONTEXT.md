# {Workspace Name} — 7-Step Autonomous Engineering Pipeline

Sequential stage execution order:

1. [01_inbox](01_inbox/CONTEXT.md) — Ingest raw requirements, user stories, and bug prompts into a feature spec.
2. [02_plan_split](02_plan_split/CONTEXT.md) — Decompose work into vertical slices and generate holdout tests.
3. [03_kanban](03_kanban/CONTEXT.md) — Target-local markdown Kanban board state machine (todo, doing, done, rejected).
4. [04_sandboxes](04_sandboxes/CONTEXT.md) — Parallel builder worker slots running in isolated git worktrees.
5. [05_gates](05_gates/CONTEXT.md) — Deterministic quality test gates (unit tests, clippy, playwright-rs).
6. [06_judge](06_judge/CONTEXT.md) — Fresh-context unbiased evaluation audit logs evaluating against spec.
7. [07_holdouts](07_holdouts/CONTEXT.md) — Anti-sycophancy holdout test suite hidden from builder agents.
