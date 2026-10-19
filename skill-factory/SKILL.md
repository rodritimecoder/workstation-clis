---
name: skill-factory
description: >
  Retrofit an existing skill into a routable, action-indexed, token-lean form.
  Use when a skill's body is prose-heavy, its routing is weak, or a new skill
  should be written from an existing CLI.
---

# `skill-factory` — retrofit skills into the `tailscale-ops` shape

Your collection has 27 skills. Every one of them spends more tokens than it
needs to, and half of their section headings are prose an agent never acts
on. This skill fixes that without deleting anything.

## The model

`tailscale-ops` already has the target shape. Read it once before you
write anything:

```bash
cat /run/media/rodri/AI/skills/tailscale-ops/SKILL.md
```

Six rules, all derived from that file:

1. **H1 is the skill id**, not a prose title.
2. **Exactly one H2**: `Commands`.
3. **H3 per action** — numbered, imperative, the CLI subcommand in parens.
4. **One line** of context per action, then the command.
5. **The command is always first** in the fence.
6. **No `Prerequisites`, no `Architecture`, no `When to use`.** The agent
   does not install, and the description already says when to use it.

## The procedure

### 1. Stage the run

```bash
python3 scripts/scaffold.py <skill-name>
```

Creates a run area under `~/.cache/skill-factory/runs/` with three stages —
`01_interview/`, `02_draft/`, `03_proof/` — each with its own `CONTEXT.md`.
Read `01_interview/CONTEXT.md` next.

### 2. Interview the skill, not the user

Read the existing `SKILL.md` and its `scripts/`. Sort every section into
one of four buckets:

| Bucket | What happens |
|---|---|
| **Action** — a command an agent would run | Stays in the body |
| **Narrative** — architecture, background, port tables | **Moves to `references/<topic>.md`** |
| **Dead weight** — prerequisites, installation, "when to use" | Deleted; the description covers the last one |
| **Broken path** — `~/.gemini/config/skills/...` | Rewritten skill-relative |

Ask the user only what you cannot read. The commands are all there.

### 3. Draft

Read `02_draft/CONTEXT.md` and the references it points to. Then write
`02_draft/SKILL.md` and curate `02_draft/aliases.json`.

The narrative is **moved, not deleted** — `references/` is already a
convention in this collection (`agent-reach` has seven files,
`canvas-cli` has `api_endpoints.md`) and `omnicli` already indexes
`references/*.md` as a separate kind, so the background is still findable
by search and still available on demand.

### 4. Gate

```bash
python3 scripts/audit.py <run-dir>/02_draft
```

The gate is deterministic and fast. It checks: frontmatter present and the
name matching the directory, description within 30 words, body within 300
words, exactly one H1, every leaf section carrying a command, no prose leaf
over 40 words, no banned section titles, no hardcoded harness paths, and
every command resolving to something that exists.

Fix what it flags. Do not raise the budget to make it pass.

### 5. Prove

```bash
python3 scripts/register.py <run-dir> --check
```

Two proofs, and a retrofit that fails either is not finished:

- **Routing.** Three *different* phrasings of the same intent must return
  the skill at position 1. One phrasing proves nothing; three prove the
  skill is findable by intent rather than by memorised wording.
- **Regression.** `omnicli eval` top-1 must not fall. Routing is shared —
  lifting one skill by demoting another is a regression, not an improvement.

### 6. Publish

```bash
python3 scripts/register.py <run-dir> --publish
```

Writes the skill, sets the alias set, reindexes, re-proves, and **rolls
back automatically** if any gate fails.

## The alias set is the routing surface

The words a user would type that appear in **no** document. `scaffold.py`
mines candidates — terms the body uses that the name and description do not
— but they need curating:

- Keep **5–12**. More is noise; fewer is a gap.
- One is a domain synonym the skill *should* match on ("podcast" for audio
  tooling, "cheat sheet" for course material).
- One is a phrase the user would use but the docs never spell out.
- **Never** a verbatim echo of a test query. `tests/overfit_check.py` in
  `omnicli` audits for exactly that, and a router handed the answer key
  measures nothing.

Alias sets are curated metadata, so they live with the catalog:

```bash
omnicli alias <skill> --aliases "a,b,c" --tags "x,y"
omnicli alias <skill> --remove
```

## Audit the whole collection

```bash
python3 scripts/audit.py --all
```

Every skill, every rule, and what it would cost to fix. It is fast enough
(under 50ms for 27 skills) to run in a hook.

## What this does not do

- It does not write wrapper scripts for capabilities that have no CLI yet.
- It does not run the commands it documents. The gate resolves them; it
  does not execute them.
- It does not touch the other skills to fix a routing miss. If a skill
  cannot win a phrasing it should have won, the fix is its own alias set.
