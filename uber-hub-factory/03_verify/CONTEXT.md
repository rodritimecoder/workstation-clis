# Stage 03: Grounded Verification

## Purpose
Rigorously verify that the bridged hub and all bridged standalone skills function correctly both through the hub and independently.

## Input
- `02_bridge/output/bridge_summary.json` (or hub name and manifest).

## Process
1. Test Hub Inspection: `<hub-name> list` returns all registered suites with exit code 0.
2. Test Hub Discovery: `<hub-name> search <intent>` returns ranked relevance matches.
3. Test Hub Contract: `<hub-name> inspect <suite>` correctly prints the suite's native `SKILL.md`.
4. Test Hub Execution: `<hub-name> run <suite> --help` (or direct `<hub-name> <suite> --help`) executes without error.
5. Test Standalone Independence: Direct execution of standalone tools (`<standalone-tool> --help`) executes with exit code 0.

## Output
- `output/verification_report.json`: Pass/fail status, test logs, exit codes, and timestamps.

## Human / Agent Check
- Ensure all 5 verification checks pass cleanly.
- Confirm zero broken links or orphaned scripts.
