# The template

The shape to copy. The example is fictional on purpose — a real skill name
in a template would put that name into the index and let the template
compete with the skills it is describing.

```markdown
---
name: <skill-name>
description: >
  <what it does, one clause> <what it is for> <when to reach for it>.
---

# <skill-name>

<One line: the capability, and its tier or fallback if it has one.>

## Commands

### 1. <imperative action> (`<subcommand>`)
<One line: when to use THIS action, not the skill in general.>
```bash
<the exact command>
```

### 2. <imperative action> (`<subcommand>`)
```bash
<the exact command with the flag that matters>
```
```

A copy of this, ready to fill in, is at
`templates/run/02_draft/SKILL.md.template`. `scaffold.py` seeds it for a
greenfield skill; for a retrofit it seeds the *current* `SKILL.md` instead,
so the job is compression rather than rediscovery.

## The shape, annotated

| Element | Why |
|---|---|
| `name:` matches the directory | The harness derives the skill id from the directory; a mismatch means the skill registers under one name and is called by another |
| Folded `description: >` | Multi-line YAML, so the description stays readable in the source |
| `# <skill-name>` | The H1 is the identifier, not a title. An agent does not need a title |
| One line of capability | Enough to orient, not enough to be a section |
| `## Commands` | The only H2. One group, so an agent can jump straight to it |
| `### N. <imperative>` | Numbered and imperative — it reads as an instruction, not a topic |
| `(<subcommand>)` | Names the exact invocation, so the agent does not have to guess |
| One line of context | The condition under which *this* command is the right one |
| The command first | The agent can execute what it reads |
| No trailing section | A skill that ends with a caveat paragraph teaches the agent to distrust it |

## Where the rest goes

Anything that does not fit the shape above goes to `references/<topic>.md`:

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
