# Routing rules

A skill that is never found does not exist, however good its body is.
Routing is decided by three things, in this order.

## 1. The name

`<domain>-<noun>`, using the noun **the user would say**, not the noun the
implementation happens to use.

| Good | Why |
|---|---|
| `zoom-recorder` | "a zoom recording" |
| `cornell-notes` | "cornell notes" |
| `guard-hooks` | "guard hooks" |
| `hybrid-browser` | "hybrid browser" |

| Bad | Why |
|---|---|
| `agentic-engineering` | Nothing a user would type |
| `litellm-vram-switcher` | A vendor and an implementation detail |
| `nvidia-nim` | A vendor |

The name is also the strongest signal in the index — it is weighted five
times higher than body prose. A name full of vendor names is a name that
will not match.

## 2. The description

Covered in `token-rules.md`. The part that matters for routing: **the
trigger phrase**. The words a user would use to ask for the thing.

## 3. The alias set — the one nobody writes

This is where a skill's vocabulary gap is closed.

**An alias is a word a user would type that appears in no document of the
skill.** The clearest case in this collection: `audiocpp`'s documentation
never says "podcast", but a user absolutely might. Before the alias set
existed, the query *"turn a recorded podcast into readable text"* routed
to a folder-architecture document and missed the audio tool entirely.

**How to curate**

1. Run `scaffold.py` — it mines candidates: terms the body uses that the
   name and description do not.
2. Keep the ones a user would plausibly type.
3. Aim for **5–12**.

**What to keep**

- A domain synonym the skill should obviously match on — "podcast" for
  audio tooling, "cheat sheet" for course material, "voice" for TTS.
- A phrase the user would use but the docs never spell out — "make it
  look less AI-generated" for a deslopping tool.
- The near-miss vocabulary: "reel" for a short video, "screenshot" for an
  image of a screen.

**What to drop**

- Anything already in the name or description. It adds nothing.
- Anything that only makes sense to the author — "swarm", "harness",
  "orchestra" are internal nouns.
- **A verbatim echo of a test query.** `omnicli`'s
  `tests/overfit_check.py` audits for exactly this. A router that has been
  handed the answer key measures nothing, and the number it reports is a
  lie.

**How to store them**

Aliases are curated metadata, so they live with the catalog, not in the
body. The body is read by agents; the alias set is read by the router.

```bash
omnicli alias <skill> --aliases "podcast,voice,speech" --tags "audio,tts"
omnicli alias <skill>                       # show
omnicli alias --list                        # every skill
omnicli alias <skill> --remove              # delete
```

## Why the alias column is weighted separately

In the catalog, aliases and tags live in their own FTS5 column at roughly
twelve times the weight of body prose. That is deliberate.

A curated alias is the skill author stating *"this vocabulary routes
here"*. A body sentence containing the same word says far less — it is
incidental, and in a large document there is always an incidental match.
Without the separation, a generic document accumulates more incidental
matches than a precise document accumulates deliberate ones, and it wins.
That is the hijack that `icm-architect` used to pull off on nearly every
query.

## Tags

Tags are categories, not synonyms. They help the router when a query
matches a domain rather than a capability — "education", "audio", "git".
They are weighted with the aliases, so keep them short and few.
