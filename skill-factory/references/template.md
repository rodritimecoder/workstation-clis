# The template

The shape to copy. The example is fictional on purpose — a real skill name
in a template would put that name into the index and let the template
compete with the skills it is describing.

The model is **`jev-decision`**, with **`swarm-contract`** as the lean
variant. Read both before writing:

```bash
cat /run/media/rodri/AI/skills/glitch-cat/jev-decision/SKILL.md
cat /run/media/rodri/AI/skills/glitch-cat/swarm-contract/SKILL.md
```

## The shape

```markdown
---
name: <id>
description: >
  <one sentence naming what it is and where it came from> <what it does>.
---

# <Display Name> (`<id>`)

<One dense paragraph: what it is, which engine backs it, where it lives,
what problem it solves.>

---

## 🏛️ <The Concept>

| <Dimension> | <Type> | <Representation> | <Example Question> |
| :--- | :--- | :--- | :--- |
| **`<mode-a>`** | <type> | <representation> | *"<a question a user would ask>"* |

---

## 🛠️ CLI Quickstart

```bash
<VAR>="python3 <path>/<script>.py"

# 1. <Action> (<mode>)
$<VAR> <subcommand> <args>
# Output: <what it returns>
```

## Annotated

| Element | Why |
|---|---|
| `name:` matches the directory | The harness derives the skill id from the directory |
| Folded `description: >` | Multi-line YAML, so it stays readable in the source |
| `# <Display Name> (`<id>`)` | The H1 is the identifier *and* a human name. Not a title |
| One dense intro paragraph | Orientation, not narrative. It states what backs the thing and where it lives, because that is what an agent needs before it picks a command |
| `## 🏛️ <Concept>` | The mental model. **A table with an example column** is the richest form: each row shows not just what a mode is, but the question a user would ask to reach for it. That column is what lets an agent act without reading more |
| `## 🛠️ CLI Quickstart` | One fence, one `$VAR` binding |
| `$VAR="python3 …"` | Binds the tool once. Every command line then starts with three characters instead of a path. It also keeps the commands short enough that the fence stays scannable |
| `# 1. <Action> (<mode>)` | The comment is the index. An agent scanning the fence reads the numbered comments and never has to parse the arguments |
| `# Output: …` | Optional but valuable — the result shape without running it |
| `---` separators | Visually break the three zones: what it is, how it works, how to run it |

## Two variants

**Lean** — `swarm-contract`. A numbered list of 2–5 bolded items instead of
a table, and no `# Output:` comments. 137 words for four commands.

**Rich** — `jev-decision`. A table with an examples column, and output
comments on every command. 410 words for nine commands.

Both are the same shape. The difference is how much the reader needs.

## Where the rest goes

Anything that does not fit goes to `references/<topic>.md`:

- architecture, ports, tier explanations → `references/architecture.md`
- long flag or option documentation → `references/options.md`
- background on a domain concept → `references/concepts.md`
- failure modes, in a table → `references/troubleshooting.md`

The body links to them in one line, so the agent knows they exist and can
ask for the one it needs:

```markdown
## Reference
- `references/architecture.md` — tiers, ports (:3010, :9222, :8088), profile path
```

The narrative is **moved, never deleted**. `omnicli` still indexes
`references/*.md`, so it stays findable by search.
