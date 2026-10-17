---
name: icm-architect
description: Design any process, idea, problem, or body of knowledge into an ICM (Interpretable Context Methodology) workspace — folder structure as agent architecture — or restructure an existing folder, repo, or vault into one. Use when the user wants to (1) turn a recurring workflow into an agent-runnable folder pipeline, (2) organize scattered notes, files, or knowledge into a library one AI agent can walk, (3) map a team or company as connected context ("context map", "second brain", "team brain", "knowledge base for AI"), (4) audit a codebase or mixed folder into a walkable edit map (objects, processes, change-impact) so later agents can change it without slurping the tree, (5) audit or restructure an existing workspace to ICM conventions, or (6) says "make this an ICM", "ICM this", "map this repo", "audit this folder", "what would a change hit", "build me a workspace", or "structure this for agents".
---

# ICM Architect

Build workspaces where the folder structure does the orchestration. One agent, reading the right files at the right moment, replaces a multi-agent framework: numbered folders carry sequencing, hierarchy carries context scoping, plain markdown files carry state. A human can open any folder and see exactly what state the system is in, because state is just files.

Think of the workspace as a library. The routing files are the catalog: small, stable, they point at everything and store almost nothing. The content lives on the shelves (stage folders, node files, reference material). One librarian — one model — walks the building, and the question decides which shelf gets walked to. Nobody photocopies the library into a backpack; that is what context-stuffing is. The catalog is small on purpose.

Method: Interpretable Context Methodology (Van Clief & McDermott, arXiv:2603.16021, MIT-licensed).

## The invariants

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

## 🛠️ CLI Quickstart (`icm-architect`)

The canonical executable is located at `~/.local/bin/icm-architect` (symlinked from `/run/media/rodri/AI/skills/icm-architect/scripts/icm_architect.py`).

### 1. Scaffold a New ICM Workspace
```bash
# Initialize a 4-stage pipeline workspace
icm-architect init ./my-pipeline --name "Course Video Production" --stages plan,extract,render,publish

# Initialize with JSON output for automated agent tooling
icm-architect init ./agent-workspace --stages ingest,filter,distill --json
```

### 2. Validate Reference Integrity & Hierarchy
```bash
# Validate current workspace structure and relative markdown links
icm-architect validate .

# Diagnostic health check with exit code gating (0 = PASS, 1 = FAIL)
icm-architect doctor /path/to/workspace --json
```

### 3. Visual Topology Mapping
```bash
# Render ASCII terminal stage flow
icm-architect map .

# Output GitHub-flavored Mermaid flowchart
icm-architect map . --mermaid
```

## Choose a mode

- **Building from a described process, idea, or problem** → Build mode.
- **An existing folder, repo, or vault that needs ICM structure** → Restructure mode.
- **A body of work later agents must edit** (code, markdown, or mixed) → System map form. Read [references/system-map.md](references/system-map.md) after picking the form.

## Build mode

**1. Extract the structure from dialogue.** The structure is already in how the person describes the work — don't impose a shape, surface theirs. Ask (a few at a time, not all at once):

- What is the repeating unit of work? (an episode, a client, a report, a person, a team?)
- Walk me through one run, start to finish. Where do you stop and check something before continuing?
- What stays the same every run (voice, rules, brand, schema) vs. what is new every run?
- What does "done" look like — what artifact leaves the workspace?
- Who else touches this, and what do they need to find without asking you?

Their pauses become stage boundaries. Their "I always check X before Y" become human gates. Their "it always has to sound like / follow Z" becomes factory reference material.

**2. Pick the form.** Read [references/forms.md](references/forms.md) and choose:

| Form | Reach for it when |
|---|---|
| **Pipeline** | The same sequence runs repeatedly, producing a deliverable each run |
| **Umbrella** | Several distinct pipelines share one brand/voice/reference layer |
| **Record library** | The unit is a record (person, client, session) that accumulates, not a run |
| **Knowledge bundle** | The product is navigable knowledge itself (a brain, a wiki, a model of something) |
| **Context map** | The subject is an organization — teams, processes, data, and the links between them |
| **System map** | A folder later agents will edit — nouns, movements, and what a change hits. Method: [references/system-map.md](references/system-map.md) |

Real workspaces mix forms (a record library whose records are mini knowledge bundles; a pipeline that emits into a record library). Compose freely — the invariants hold at every level, recursively.

**3. Scaffold the smallest structure that carries the work.** Copy starters from [assets/templates/](assets/templates/) and fill them in. Do not create folders for stages that don't exist yet, empty "misc" buckets, or speculative depth. Three real stages beat seven imagined ones. If the whole job fits in one saved prompt, say so and don't build a workspace at all.

**4. Write the contracts.** Root `AGENTS.md` (identity + negative routing + folder map + status rules + routing table), root `CONTEXT.md` (the pipeline or schema definition), one `CONTEXT.md` per stage/hub folder, `setup/questionnaire.md` if the factory needs configuring per user. Write inputs as explicit file paths, split into working (this run) and reference (every run). Copy [assets/templates/AGENTS.md](assets/templates/AGENTS.md) as the starting point — it already carries the "Not this workspace", `STALE`, and re-run sections.

**5. Validate with the walk test** (below).

## Restructure mode

**1. Inventory before touching.** List the tree. For each area note: what it is, when last touched, what refers to it. Never delete or move in this pass.

**2. Find the hidden form.** Ask the owner (or infer and confirm): what is the repeating unit here? Where does work enter and leave? The mess usually contains a real pipeline, library, or map that grew without a skeleton — extract it, don't replace it. Interview the folder the way you'd interview the person.

**3. Classify every file** into one of five roles:
- **Catalog** — identity/routing (becomes or feeds `AGENTS.md` / index files)
- **Contract** — describes how a step works (becomes a `CONTEXT.md`)
- **Factory** — stable reference (→ `_shared/`, `_system/`, or `references/`)
- **Product** — run-specific artifacts (→ stage `output/` or record folders)
- **Dead** — stale, duplicated, or superseded (→ propose `_archive/`, never silently delete)

**4. Propose before moving.** Write the target tree and a migration map (old path → new path → role) to a file in the workspace — `_migration/map.md` — and state it in your reply. Do not block waiting for a reply; the map is the reviewable artifact, and it is what a human reads if they want to. Before any move, enumerate what points at each file: in-vault references, sibling `../` paths, symlinks, and external referrers (deploy scripts, cron, agent configs) that no walk test can see. A file with a live referrer is **held** until every referrer moves with it. See [references/reference-integrity.md](references/reference-integrity.md).

**5. Migrate.** Move files, write the entry file and contracts, de-duplicate toward one-home-per-fact (leave a link where the copy lived if anything might reference it). Separate method from instance: if the structure will be reused elsewhere, the blank template lives apart from this filled-in deployment.

**6. Validate with the walk test.**

## The walk test

Validate any ICM — new or restructured — by walking it cold, as an agent with no memory:

- Open the root. Can you answer *where am I* and *where do I go for the current task* within the entry file plus at most two more reads?
- Pick any stage/node. Does its contract name exact input paths, the job, the output, and the human check?
- Can you state pipeline status purely by scanning what exists in `output/` folders (or node frontmatter)? A `COMPLETE`/`PENDING` split is not enough — a stage whose output predates its input's newest edit is `STALE`, and the entry file must say how to detect that.
- If the workspace is about to be re-run or restarted, is there a documented non-destructive path? “Clear the output folders” is not one — the entry file must say how to keep runs side by side or overwrite a single stage.
- Is any routing file carrying content payload? Move the payload to a shelf; leave a pointer.
- Is any fact stored in two places? Pick one home; link from the other.
- Token check: entry file + one contract + its inputs should land in roughly 2k–8k tokens.
- System map only: can a cold agent answer *what is X* and *what else moves if I change X* from `map/AGENTS.md` plus one card? Extra checks are in [references/system-map.md](references/system-map.md).

If a step fails, fix the structure — not by explaining more, but by moving or splitting files until the walk works.

## Guardrails

- **Don't over-structure.** The ladder runs: chat → saved prompt/skill → folders + one agent. Only climb when the rung below is genuinely automated and repeating. A workspace for a thing done twice is scaffolding, not architecture.
- **Know where ICM loses.** Real-time multi-agent collaboration, high-concurrency multi-user serving, and automated mid-pipeline branching genuinely need framework code. ICM is for sequential, human-reviewed, repeatable work — which is most knowledge work, but not all of it.
- **Anti-patterns seen in the wild:** duplicated entry files that drift (generate one from the other, or make one a pointer); schema documents that mandate names the actual files stopped using (update the schema or the files — pick one); hand-edits to generated indexes; workshop sessions that produce slides instead of structured data (every working session should end in an artifact the structure can hold); patterns declared top-down (one team complaining is a gripe — the same shape appearing three independent times is structure).

## References

- [references/core.md](references/core.md) — the five design principles, the five-layer context hierarchy, naming conventions, token discipline. Read when writing contracts or when a structural call is contested.
- [references/forms.md](references/forms.md) — the six forms in depth: skeletons, moves, failure modes. Read at step 2 of Build mode or step 2 of Restructure mode.
- [references/system-map.md](references/system-map.md) — audit pipeline for the System map form. Read when that form is chosen.
- [references/reference-integrity.md](references/reference-integrity.md) — the move-safety gate: what to search before moving or deleting a file, destination-collision checks, copy-verify-then-remove. Read before any Restructure migration or any removal of an `output/` folder.
- [references/method-paper.md](references/method-paper.md) — the original ICM paper (Van Clief & McDermott, arXiv:2603.16021). Read only when asked why/how the method works or for its original framing.
- [references/examples/system-map-code-project/](references/examples/system-map-code-project/) — worked mini System map of a code project (catalog, object cards, one process card, change-impact index). Use as the calibration example when the subject tree is code.
- [references/examples/](references/examples/) — three complete real workspaces (`course-deck-production`, `script-to-animation`, `voice-driven-animation`) plus `workspace-builder` (an ICM that builds ICMs). All use AGENTS.md as the root entry file. Consult one when calibrating how detailed a real stage contract, questionnaire, or factory layer should be.
- [assets/templates/](assets/templates/) — copyable starters: `AGENTS.md`, workspace `CONTEXT.md`, `stage-CONTEXT.md`, `node.md`, `object.md`, `process.md`, `schema.md`, `questionnaire.md`.
