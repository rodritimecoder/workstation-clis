---
name: craft-hub
description: >
  The DoorDash API for Code Craft, Audits, and Rigorous Reviews. Late-binding dispatch
  hub for 5 elite engineering kitchens: Ponytail (minimal diff & YAGNI), pstack (23 playbooks),
  Poteto Mode (domain modeling & discipline), Thermo-Nuclear (harsh architectural audit),
  and Unslop (31 AI tell elimination rules). Use whenever asked to review code, audit
  a repo or pull request, check git diffs, run "doordash", clean up AI writing slop,
  apply ponytail/pstack/poteto, or when an agent needs high-leverage code quality enforcement
  without bloating the context window. Provides CLI commands: `craft-hub` and `doordash`.
---

# Code Craft & Review Hub (`craft-hub` / `doordash`)

`craft-hub` is the specialized "DoorDash API" for high-leverage code reviews, architecture audits, and quality enforcement. Instead of polluting context windows with thousands of lines of review prompts, agents order on-demand from 5 elite engineering kitchens.

---

## 🍽️ The Kitchens & Specialty Stations Menu

| # | Kitchen ID | Specialty & Core Philosophy |
|---|---|---|
| 🍔 | **`ponytail`** | **Lazy Senior Dev & YAGNI**: Deletion beats addition, smallest complete change, no unasked-for wrappers or boilerplate. |
| 🍣 | **`pstack`** | **Rigorous Agent Playbooks**: 23 execution playbooks (Investigation, Hillclimbing, Runtime Forensics, Babysit, Shipping). |
| 🥗 | **`poteto`** | **Foundational Discipline**: Model the domain in types/state machines, laziness protocol, verified artifacts. |
| 🍕 | **`thermonuclear`** | **Harsh Architectural Audit**: Anti-spaghetti conditionals, 1,000-line ceiling, structural "code judo" deletions. |
| 🍜 | **`unslop`** | **AI Tell Elimination**: 31-rule scanner cutting superficial -ing clauses, corporate hedging, and robotic tone. |
| 🔬 | **`create-verification`** | **Verification Generator**: Generates project-local verification skill (`verify-<app>`) with Launch, Doctor, Drive, Evidence, Cleanup & Feature Map. |
| 🧪 | **`maintain-verification`** | **Verification Upkeep**: Periodic drift audit driving every mapped feature live, checking health, and catching regressions. |
| ✂️ | **`no-comments`** | **Comment Sicko**: Strips useless code comments and AI explanations; encodes real constraints into types or runtime assertions. |
| 🛡️ | **`typescript`** | **TypeScript Best Practices**: Discriminated unions, branded types, constructive modeling, zero `as` casts, schemas before guards. |

---

## 🚀 CLI Commands (`craft-hub` or `doordash`)

### 1. View the Menu
```bash
craft-hub menu
# or
doordash menu
```

### 2. Search by Intent
```bash
craft-hub search "harsh audit"
craft-hub search "delete bloat"
craft-hub search "ai writing tells"
```

### 3. Inspect a Kitchen's Rubric & Rules
```bash
craft-hub inspect ponytail
craft-hub inspect thermonuclear
craft-hub inspect pstack
craft-hub inspect unslop
```

### 4. Place an "Order" (Run Review on Diff, File, or Repo)
```bash
# Review current git diff for minimal size & YAGNI
craft-hub order ponytail

# Harsh review against 1,000-line ceiling & spaghetti logic
craft-hub order thermonuclear

# Scan markdown or docs for 31 AI tell patterns
craft-hub order unslop README.md

# Run all 5 kitchens in a single comprehensive gauntlet
craft-hub order combo
```
