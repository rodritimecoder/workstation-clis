---
name: craft-hub
description: >
  The Uber Protocol & DoorDash Gateway for Code Craft, Audits, and Rigorous Reviews. Late-binding
  dispatch hub for 9 elite engineering kitchens: Ponytail (minimal diff & YAGNI), pstack (23 playbooks),
  Poteto Mode (domain modeling & discipline), Thermo-Nuclear (harsh architectural audit),
  Unslop (31 AI tell elimination rules), Verification, No-Comments, and TypeScript. Provides
  full pre-flight response projection (--project) and disk buffering (--out) to eliminate context bloat.
---

# Code Craft & Review Hub (`craft-hub` / `doordash`)

`craft-hub` is the specialized **Uber Protocol & DoorDash Gateway** for high-leverage code reviews, architecture audits, and quality enforcement. Instead of polluting context windows with thousands of lines of prompt rules, agents discover and dispatch audits on-demand with pre-flight response projection.

---

## 🍽️ The 9 Kitchens & Specialty Stations

| # | Kitchen ID | Specialty & Core Philosophy |
|---|---|---|
| 🍔 | **`ponytail`** | **Lazy Senior Dev & YAGNI**: Deletion beats addition, smallest complete change, no unasked-for wrappers or boilerplate. Sub-recipes: `ponytail-review` (diff review), `ponytail-audit` (repo audit), `ponytail-debt` (shortcut/todo tracking), `ponytail-gain` (benchmark savings). |
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

### 1. View Menu & Kitchens
```bash
craft-hub menu
# Or structured JSON
craft-hub menu --json
```

### 2. Search Kitchens by Intent
```bash
craft-hub search "harsh audit"
craft-hub search "delete bloat"
craft-hub search "ai writing tells"
```

### 3. Inspect a Single Rubric (Zero Startup Context Freight)
```bash
craft-hub inspect ponytail
craft-hub inspect thermonuclear
craft-hub inspect typescript
```

### 4. Dispatch a Review Order with Response Projection & Disk Buffering
```bash
# Basic run on current git diff
craft-hub order ponytail

# Harsh review with output buffered to disk (keeps agent context lean)
craft-hub order thermonuclear --out /tmp/audit.json

# Run all kitchens (Combo Platter) with field projection
craft-hub order combo --project "status,checks"

# Scan markdown or docs for 31 AI tell patterns
craft-hub order unslop README.md
```
