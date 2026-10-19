---
name: skill-factory
description: >
  Retrofit an existing skill into a routable, action-indexed, token-lean form.
  Use when a skill's body is prose-heavy, its routing is weak, or a new skill
  should be written from an existing CLI.
---

# Skill Factory (`skill-factory`)

A retrofit factory for this workstation's skills. It compresses a skill to the
house shape — a concept model plus one CLI quickstart — moves its prose into
`references/`, curates the alias set that makes it findable, and proves the
result still routes before publishing. Nothing is deleted: the narrative is
moved, and `omnicli` still indexes it.

---

## 🏛️ The Retrofit Loop

| Stage | Question it answers | What it produces |
| :--- | :--- | :--- |
| **Interview** | What does this skill actually do? | The command list, and the prose to move |
| **Draft** | What is the minimum that still works? | `SKILL.md` in the house shape, plus `aliases.json` |
| **Gate** | Does it obey the rules? | A pass or fail, with the offending line |
| **Prove** | Can it still be found? | Three phrasings returning it at #1, and no regression |
| **Publish** | Can it go live safely? | The skill, its aliases, and a rollback path |

---

## 🛠️ CLI Quickstart

```bash
SF="/run/media/rodri/AI/skills/skill-factory/scripts"

# 1. Audit one skill against the nine rules
python3 $SF/audit.py /run/media/rodri/AI/skills/<skill>

# 2. Audit the collection and see what is reclaimable
python3 $SF/audit.py --all --summary

# 3. Stage a run: interview → draft → proof
python3 $SF/scaffold.py <skill>

# 4. Gate the draft
python3 $SF/audit.py ~/.cache/skill-factory/runs/<skill>-*/02_draft --expect-name <skill>

# 5. Prove routing, and check nothing else regressed
python3 $SF/register.py ~/.cache/skill-factory/runs/<skill>-* --check

# 6. Publish, rolling back automatically if a gate fails
python3 $SF/register.py ~/.cache/skill-factory/runs/<skill>-* --publish

# 7. Curate a skill's routing metadata
omnicli alias <skill> --aliases "a,b,c" --tags "x,y"
```

---

## 📐 The Rules

Nine rules, all derived from this collection's own best example rather than
invented. The details are in `references/token-rules.md`,
`references/routing-rules.md` and `references/path-rules.md`.

**The gate measures shape, not size.** A skill passes when every leaf
section is one of four things:

| Leaf | What it is |
| :--- | :--- |
| **Action** | carries a command the agent can run |
| **Concept** | a table, a numbered or bolded-lead list, or an ASCII diagram: the mental model |
| **Contract** | a JSON or YAML block: the shape the agent has to produce |
| **Reference** | a pointer at a file in `references/` |

Anything else is unclassified, and that is the only thing the gate objects
to. *How long* a section is not a defect — an omnicli-routed agent never
reads the body at all, because the contract comes from the script's own
`--help`. A word budget made the gate noisy and the work slower without
making anything better, so it is gone.

What is still checked, because each one is a real failure: frontmatter
present and the name matching the directory; no hardcoded harness paths;
every command resolving to something that exists; the banned section titles
(`Prerequisites`, `Setup`, `Overview`, `When to use`); and a warning when an
alias contains a generic word.

The rules are structural, which is what lets the whole collection be audited
in under 60 milliseconds.
