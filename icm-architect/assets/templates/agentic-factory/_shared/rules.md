# Core Engineering Rules & Team Axioms

## Invariant Axioms (Glitch Cat / Kem Software Factory)
1. **Code Decides Wherever It Can**: Unit tests, type checks, and linter gates make the decision. LLMs only decide where code cannot.
2. **Anti-Sycophancy via Holdouts**: Holdout tests in `holdouts/` are hidden from builder agents until validation.
3. **Validation Precedes Code Review**: Grounded functional verification (UI, API, persona tests) runs first. Code review runs strictly second.
4. **Human Intent Gate**: The human operator reviews the initial plan and validates the intent at the end.
5. **One State Machine per Repo**: Stage `output/` mtimes and the Kanban folders are the state. Do not add a second ledger that can disagree with them.
