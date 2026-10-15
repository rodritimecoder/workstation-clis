# 04_verify_and_sync — Grounded Verification, Purge & Push

## Purpose
Run grounded verification checks against the generated hub, purge obsolete standalone skill directories, and synchronize across all harnesses and git remotes.

## Inputs
- Scaffolding report from Stage 02
- Shims report from Stage 03

## Process
1. Run Grounded Verification:
   - `<hub-name> list`
   - `<hub-name> inspect <suite>`
   - `<hub-name> run <suite> [help/test]`
2. Delete obsolete standalone skill directories from:
   - `/run/media/rodri/AI/skills/`
   - `/run/media/rodri/AI/workstation-clis/` (if public)
3. Propagate and mirror via:
   - `sync-skills --push` (uses `--delete` to wipe stale downstream folders in `~/.gemini/` and `~/.pi/`)
4. Commit and push `workstation-clis` if applicable.

## Outputs
- `output/VERIFICATION.md`: Grounded verification transcript.
- Clean git status across repositories.

## Human / Agent Check
- Confirm `git status` is clean and zero doubled-up `SKILL.md` files exist downstream.
