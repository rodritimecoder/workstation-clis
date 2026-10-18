# 05_gates — Deterministic Quality Gates

One job: Enforce automated test suites ('Code Decides').

## Inputs
- Working: Worker branch changes from `../04_sandboxes/`
- Reference: ../_shared/rules.md

## Process
1. Run linters, type checks, and test runner.
2. Run sub-second UI checks via `playwright-rs` / `fast-cdp`.
3. Emit pass/fail status.

## Outputs
- `output/gate_results.json`

## Human check
Review test summary if failures occur.
