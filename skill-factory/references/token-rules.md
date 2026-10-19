# Token rules

Where a skill's tokens go, and which of those places you can control.

| Cost | When it is paid | Can you control it? |
|---|---|---|
| **Frontmatter** | Every turn, for every skill, whether or not it is used | Yes — this is the expensive one |
| **Body** | Once, after the skill is selected | Yes |
| **Alias set** | Never — it is not in any context window | Yes, and it decides whether the skill is ever found |

## Frontmatter: the description is on every turn

`omnicli` reads the **full body** of every skill, so a long description is
not the only cost of a vague one — it is also the cost of a bad one. But
the description is what a harness shows at turn 0, and that shelf is paid
every single turn.

**Budget: 30 words.** Up to 40 for a skill that must disambiguate itself
from a sibling (`agent-reach` versus a generic search tool).

**Shape:** what it does, what it is for, when to reach for it. In that
order, in one clause each.

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

**Budget: 300 words.** `tailscale-ops` is 301 and is the model.

**Every leaf section carries a command.** A heading whose content has no
command is prose the agent skipped. If the prose is worth keeping, it
belongs in `references/` — where `omnicli` still indexes it, and the agent
loads it only when it needs it.

**The command comes first.** No preamble, no "to do X, first ensure Y".
The agent can read a command; it cannot read an essay and then remember
the command.

```markdown
### 2. Check if a Specific Host/Port is Reachable
Before routing heavy jobs to a remote GPU host, verify both the node and target port respond:
```bash
tailscale-ops check-port <hostname-or-ip> <port>
```
```

One line of context. One command. Done.

## What to omit entirely

| Section | Why it is dead weight |
|---|---|
| `Prerequisites` | The agent does not install anything |
| `Installation` / `Setup` | Same |
| `When to use this skill` | The description says this, and the agent already chose the skill |
| `Architecture` | Interesting to the author, irrelevant at the moment of action — and it moves to `references/` intact |
| `Troubleshooting` | Unless it is one line per failure; a table of failure modes is a reference doc |
| Flag tables | `omnicli describe` extracts the real contract from `--help`. Document only the flags that change behaviour. |

## The rule that does the work

**Move, do not delete.** Every word of narrative that a future agent might
need has somewhere to go: `references/<topic>.md`, a convention already
used by `agent-reach` (seven files) and `canvas-cli`
(`api_endpoints.md`). The prose is preserved verbatim, with its heading.
It simply stops being paid for on every selection.

The collection currently has **5,771 words of prose over budget** — that is
the reclaimable pool, and it is not a deletion.
