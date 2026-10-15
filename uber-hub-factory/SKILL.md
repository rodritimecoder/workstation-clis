---
name: uber-hub-factory
description: Autonomous ICM pipeline and CLI factory that consolidates scattered agent skills into unified, late-binding Uber API Hubs. Automatically maps callers, renames nested SKILL.md files to prevent registration bloat, generates backward-compatible ~/.local/bin/ shims, and handles zero-drift push synchronization.
---

# `uber-hub-factory` — Autonomous Skill Consolidation & Hub Factory

An automated **Interpretable Context Methodology (ICM)** workspace and CLI for consolidating scattered skills into unified, high-performance Uber API Hubs.

---

## ⚡ The Problem It Solves

When multiple specialized tools exist in separate folders, each with its own `SKILL.md`:
1. **Context Window Rot**: The AI agent's system prompt loads dozens of repetitive skill definitions.
2. **Double Maintenance**: Separate scripts, separate sync pipelines, and drift between harnesses.
3. **Manual Overhead**: Consolidating manually requires tracing callers, building CLI dispatchers, renaming files to avoid duplicates, and creating shell shims.

`uber-hub-factory` runs this consolidation deterministically in a 4-stage pipeline.

---

## 🚀 CLI Usage

### 1. Build / Consolidate Skills into a Hub
```bash
# Consolidate multiple skills into a single hub
uber-hub-factory build --hub academic-hub --skills canvas-cli,zoom-recorder,cornell-notes,markitdown-cli

# Dry-run inventory pass without modifying disk
uber-hub-factory inventory --skills ocr-cli,jev-cli,audiocpp-asr
```

### 2. Stages Executed by the Factory
1. **Stage 1 (Inventory)**: Inspects source skills, maps all executable scripts, extracts rubrics, and identifies callers across the workstation.
2. **Stage 2 (Scaffold)**: Deploys the generic Uber API runner (`list`, `search`, `inspect`, `run`, `--project`, `--out`), moves files into `suites/`, and renames nested `SKILL.md` to `rubric.md` (preventing prompt bloat).
3. **Stage 3 (Shimming)**: Automatically creates shell wrappers in `~/.local/bin/` so old CLI commands continue working without breaking existing pipelines.
4. **Stage 4 (Verify & Sync)**: Runs health checks, deletes obsolete standalone folders upstream and downstream, and pushes to GitHub via `sync-skills --push`.
