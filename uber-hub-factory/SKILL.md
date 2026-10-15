---
name: uber-hub-factory
description: "Non-destructive ICM bridge pipeline and CLI factory that unifies native standalone skills into late-binding Uber API Hubs. Preserves standalone skills, native SKILL.md files, and existing CLIs while providing late-binding search, list, inspect, and response projection."
---

# `uber-hub-factory` — Non-Destructive ICM Hub Bridge

An automated **Interpretable Context Methodology (ICM)** workspace and CLI for bridging standalone skills into unified, late-binding Uber API Hubs without moving, swallowing, or deleting source skills.

---

## ⚡ Non-Destructive Bridge Pattern

Traditional consolidation forced moving folders into `suites/`, deleting standalone skills, and renaming `SKILL.md` to `rubric.md` to save a negligible token margin—creating maintenance friction and breaking standalone CLIs.

**The Bridge Pattern preserves standalone integrity:**
1. **Zero Deletions**: Standalone skills keep their native directories, `SKILL.md` files, and independent CLI shims intact.
2. **Dynamic Sibling Resolution**: The bridged hub resolves contracts from `../<skill>/SKILL.md` and delegates execution to `../<skill>/scripts/` or system PATH.
3. **Dual Execution**: Skills can be invoked directly (`canvas-cli`, `zoom-recorder`) OR via the hub (`academic-icm run canvas` or `academic-icm canvas`).
4. **Late-Binding Freight Savings**: Agents inspect contracts on demand (`<hub> inspect <skill>`) and buffer outputs (`--out / --project`) without polluting context.

---

## 🚀 CLI Usage

### 1. Bridge Skills into a Unified Hub
```bash
# Bridge multiple standalone skills into a unified hub
uber-hub-factory bridge --hub academic-icm --skills canvas-cli,zoom-recorder,cornell-notes

# Discover skills and generate manifest only (Stage 1)
uber-hub-factory discover --skills canvas-cli,zoom-recorder,cornell-notes

# Run grounded verification on an existing hub (Stage 3)
uber-hub-factory verify --hub academic-icm
```

---

## 📂 The 3-Stage ICM Architecture

| Stage | Name | Role | Output |
|---|---|---|---|
| `01_discover/` | Discover & Map | Scans standalone skills, extracts `SKILL.md` descriptions, CLI entrypoints, and callers. | `output/manifest.json` |
| `02_bridge/` | Bridge & Scaffold | Generates non-destructive router `<hub>.py`, `SKILL.md`, `README.md`, and links `~/.local/bin/<hub>`. | `output/bridge_summary.json` |
| `03_verify/` | Grounded Verification | Proves hub `--help`, `list`, `search`, `inspect`, and delegated execution; confirms standalone skills remain intact. | `output/verification_report.json` |
