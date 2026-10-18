# 07_holdouts — Anti-Sycophancy Test Suite

One job: Maintain secret validation tests builder agents never see.

## Inputs
- Working: Holdout scenarios defined during planning
- Reference: ../_shared/rules.md

## Process
1. Store holdout test scripts and edge case fixtures.
2. Accessible ONLY to `06_judge` at validation time.

## Outputs
- `output/holdout_pass.log`

## Human check
Confirm holdouts test true user behavior, not implementation details.
