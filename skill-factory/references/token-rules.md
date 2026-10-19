# Token rules

Where a skill's tokens go, and which of those places you can control.

| Cost | When it is paid | Can you control it? |
|---|---|---|
| **Frontmatter** | Every turn, for every skill, whether or not it is used | Yes — this is the expensive one |
| **Body** | Once, after the skill is selected | Yes |
| **Alias set** | Never — it is not in any context window | Yes, and it decides whether the skill is ever found |

## Frontmatter: the description is on every turn

`omnicli` reads the **full body** of every skill, so a long description is
not the only cost of a vague one — it is also the cost of a bad one. But the
description is what a harness shows at turn 0, and that shelf is paid every
single turn.

**Aim for around 50 words.** The house style runs 41–53 (median 41), so
that is the house, not a squeeze. Five skills exceed it and all five are
genuinely wrong rather than house-styled: `icm-architect` 147,
`agent-reach` 121, `audiocpp` 75, `review-hub` 66, `guard-hooks` 63.

The gate *warns* about a long description rather than failing it. A tight
one is nicer — the shelf is paid every turn — but the thing that actually
decides routing is the alias set, and gating on a word count there bought
nothing.

**Shape:** what it is, what it is for, when to reach for it. In that order,
in one clause each.

```yaml
description: >
  Download Zoom cloud recording transcripts, audio, and keyframe slides.
  Use for lecture recordings, passcode-protected links, or extracting
  slides from a recording.
```

**Not this** — 36 words of capability list with no trigger:

```yaml
description: >
  Tiered browser automation agent using Podman Chromium, Chrome DevTools
  Protocol (CDP), and DeskForge-Qwen3.5-4B visual grounding fallback.
  Use whenever asked to browse the web, interact with authenticated web
  portals, click complex canvas/SVG buttons, or automate web flows.
```

That one is a capability inventory. The reader cannot tell from it whether
*this* is the skill to reach for. Cut the implementation names, keep the
trigger.

## Body: read once, but only if the agent acts on it

The body is read after the skill is selected. The agent arrives knowing
what it wants to do, so the body's job is to get out of the way.

**There is no word budget.** A body of a few thousand words is a signal
that something was pasted in, and that is the only thing worth catching.

The reason matters: an omnicli-routed agent never reads the body. The
contract comes from the script's own `--help`, extracted once at index time
and served by `omni_describe`. A body budget therefore gates on a cost
nobody pays, and it made the gate noisy and the work slower without making
anything better.

What *does* matter is the shape — every leaf section is an action, a
concept, a contract, or a pointer into `references/`.

### The concept section is where prose belongs

A concept section is the mental model: **a table**, or a **numbered list of
2–5 bolded items**. It is the one place prose is allowed to live, because
it is what tells an agent *which* command to reach for.

`jev-decision`'s table is the richest form, and its last column is the
important one:

| Primitive | Output Type | Representation | Example Decision Question |
| :--- | :--- | :--- | :--- |
| **`bool`** | Binary boolean | `true`/`false` + confidence | *"Does claim B supersede or negate claim A?"* |

**"Example Decision Question" is the column that makes it work.** Each row
shows not just what a mode is, but the question a user would ask to reach
for it. Without that column the table is documentation; with it, it is
routing.

An earlier version of these rules *banned* `Architecture` as a section
title, and counted concept sections as prose. That was wrong, and it
inflated the measured backlog by 3x.

### Every other section is an action

A leaf section is either a concept, or it carries a command (or points at a
reference file). Anything else is prose that should move to `references/`.

**The command comes first.** No preamble, no "to do X, first ensure Y".
The agent can read a command; it cannot read an essay and then remember
the command.

```bash
# 1. Check if a Specific Host/Port is Reachable
# Before routing heavy jobs to a remote GPU host, verify node and port respond:
$TS check-port <hostname-or-ip> <port>
```

One line of context, one command, in a single fence.

## What to omit entirely

| Section | Why it is dead weight |
|---|---|
| `Prerequisites` | The agent does not install anything |
| `Installation` / `Setup` | Same |
| `When to use this skill` | The description says this, and the agent already chose the skill |
| `Architecture` | **Not dead weight — it is the concept section.** It moves to `references/` only if it is not a table or a short list |
| `Troubleshooting` | Unless it is one line per failure; a table of failure modes is a reference doc |
| Flag tables | `omnicli describe` extracts the real contract from `--help`. Document only the flags that change behaviour. |

## The rule that does the work

**Move, do not delete.** Every word of narrative that a future agent might
need has somewhere to go: `references/<topic>.md`, a convention already
used by `agent-reach` (seven files) and `canvas-cli`
(`api_endpoints.md`). The prose is preserved verbatim, with its heading.
It simply stops being paid for on every selection.
