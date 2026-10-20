---
name: icm-architect

description: >
  Design a process, idea, or codebase into an ICM workspace, or restructure an
  existing folder, repo, or vault into one. Use when the user wants
  agent-runnable folder pipelines, a context map, or an audit of what a change
  would hit.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires network access to the model endpoints its scaffolding targets."
metadata:
  author: "rodri"
allowed-tools: "Bash(icm-architect:*) Bash(python3:*) Read Write"
---

# ICM Architect (`icm-architect`)

Build workspaces where the folder structure does the orchestration. One agent, reading the right files at the right moment, replaces a multi-agent framework: numbered folders carry sequencing, hierarchy carries context scoping, plain markdown files carry state. A human can open any folder and see exactly what state the system is in, because state is just files.

Think of the workspace as a library. The routing files are the catalog: small, stable, they point at everything and store almost nothing. The content lives on the shelves (stage folders, node files, reference material). One librarian — one model — walks the building, and the question decides which shelf gets walked to. Nobody photocopies the library into a backpack; that is what context-stuffing is. The catalog is small on purpose.

Method: Interpretable Context Methodology (Van Clief & McDermott, arXiv:2603.16021, MIT-licensed).

---

## The Invariants

Every ICM, whatever its form, obeys these. When building or restructuring, enforce all ten:

1. **One folder, one job.** Each folder does a single step or holds a single kind of thing, and states its own purpose in a file inside itself. The structure is the documentation.
2. **A small, stable entry file.** `AGENTS.md` at the root answers "where am I, where does everything live, where do I go for task X" — and nothing else. Target under ~60 lines. It routes; it never holds content. It also carries two things a routing table alone cannot: a **"Not this workspace"** section (what this workspace is *not* for, and where those requests go instead), and the **status** rules below, including `STALE`.
3. **Numbering encodes order.** `01_`, `02_`, … where sequence matters. Renaming folders reorders the pipeline — that is the point.
4. **Every folder-level contract is explicit.** A `CONTEXT.md` per working folder: what it reads (inputs), what it does (process), what it writes (outputs), what a human checks. See [assets/templates/stage-CONTEXT.md](assets/templates/stage-CONTEXT.md).
5. **Factory vs. product.** Reference material (rules, voice, schemas, templates — stable across runs) lives structurally apart from working artifacts (outputs, drafts — new every run). Configure the factory once; the product is what each run emits.
6. **Every output is an edit surface.** Intermediate outputs are plain files a human can open, edit, and save before the next step reads them. A human *may* review a stage's output before the next one starts — that is a choice at the handoff, not a lock on the pipeline.
7. **Load only what the step needs.** An agent executing a step reads its contract, its references, and its inputs — not the whole workspace. 2,000–8,000 tokens per step is the healthy range.
8. **Plain text, linkable, queryable.** Markdown + YAML frontmatter. Links (`[[wikilinks]]` or relative paths) make it a graph; frontmatter labels make it queryable. One home per fact — a link beats a copy.
9. **The filesystem is the state machine.** "Status" is derivable by scanning what exists in output folders. A stage with output newer than the previous stage's output is `COMPLETE`; output older than it is `STALE`, because someone edited an upstream file after this stage ran. Presence alone cannot tell those apart. Generated indexes (file maps, logs) are rebuilt by script, never hand-edited.
10. **Instantiate by copying.** New unit of work = copy a template folder, not a blank page. Keep templates in a `_templates/` or `_system/` folder.

---

## 🏛️ Choose a Mode

| Situation | Mode | Example request |
| :--- | :--- | :--- |
| A described process, idea, or problem | **Build** | *"Build me a workspace for a video course pipeline"* |
| An existing folder, repo, or vault needing structure | **Restructure** | *"Turn this notes repo into an ICM"* |
| A body of work later agents will edit | **System map** | *"Map this codebase so I know what a change hits"* |

---

## 🛠️ CLI Quickstart

```bash
# 1. Scaffold a new ICM workspace
icm-architect init ./my-pipeline --name "Course Video Production" --stages plan,extract,render,publish --with-memory

# 2. Validate reference integrity and hierarchy
icm-architect validate .

# 3. Diagnostic health check, with exit code gating (0 = PASS, 1 = FAIL)
icm-architect doctor /path/to/workspace --json

# 4. Render the stage flow as an ASCII topology
icm-architect map .

# 5. Same, as a GitHub-flavoured Mermaid flowchart
icm-architect map . --mermaid
```

---

## Reference

- `references/build-mode.md` — extracting the structure, picking a form, writing the contracts
- `references/restructure-mode.md` — mapping an existing workspace before you touch it
- `references/walk-test.md` — validating any ICM by walking it cold, as an agent with no memory
- `references/guardrails.md` — what not to do while restructuring
