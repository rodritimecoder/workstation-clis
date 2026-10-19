#!/usr/bin/env python3
"""scaffold.py — create a staged run area for a skill retrofit.

A run is a mini-ICM: numbered stages, one CONTEXT.md each, so an agent
loads only the context its current stage needs.

    01_interview/   what am I interviewing?   (the existing skill)
    02_draft/       what am I writing?         (→ references/)
    03_proof/       what am I proving?         (routing + regression)

For a retrofit the draft is seeded with the *current* SKILL.md and the
*current* aliases, so the job is compression rather than rediscovery.

    scaffold.py hybrid-browser
    scaffold.py new-thing --template
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

COLLECTION = Path("/run/media/rodri/AI/skills")
RUNS_ROOT = Path(
    os.environ.get("SKILL_FACTORY_RUNS")
    or (Path.home() / ".cache" / "skill-factory" / "runs")
)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "run"

INTERVIEW_CONTEXT = """# CONTEXT — Interview

**Where am I?** Retrofitting `{skill}`.

**What am I reading?** The existing skill, in this order:
1. `{skill}/SKILL.md` — the current body. Every command here is real and
   must survive the retrofit.
2. `{skill}/scripts/` — the executables. Their `--help` is the contract.
3. `{skill}/references/` — narrative that already has a home.

**What am I looking for?**

| | |
|---|---|
| Actions | The commands an agent would actually run. These stay in the body. |
| Narrative | Architecture, background, port tables, conceptual explanation. These move to `references/`. |
| Dead weight | Prerequisites, installation, "when to use this skill". The description already covers the last one; the agent does not install. |
| Broken paths | Absolute harness paths (`~/.gemini/config/skills/...`) that only resolve by accident. |

**What must not change?** The commands. A retrofit that renames a flag or
drops an action is a regression, not a cleanup.

Do not ask the user what you can read. Read it.
"""

DRAFT_CONTEXT = """# CONTEXT — Draft

**Where am I am I?** Writing the `{skill}` body.

**What rules apply?** Read `references/token-rules.md` for what to write and
what to omit, and `references/routing-rules.md` for the description and the
alias set. The shape to copy is `tailscale-ops` — read it once:

    cat {collection}/tailscale-ops/SKILL.md

**What am I producing?** `SKILL.md` and `aliases.json` in this folder.

**The shape**

```markdown
---
name: {skill}
description: >
  <one clause: what it does> <what it is for> <when to reach for it>
---

# {skill}

<one line: the capability, and its tier or fallback if it has one>

## Commands

### 1. <imperative action> (`<subcommand>`)
<one line: when to use THIS action>
```bash
<the exact command>
```
```

**The order of work**
1. Move every narrative section to `references/<topic>.md`. Preserve it.
2. Rewrite the description to at most 30 words.
3. Reorder the actions so the common ones come first.
4. Replace absolute harness paths with skill-relative ones.
5. Curate the alias set — see `references/routing-rules.md`.
6. Run the gate: `python3 scripts/audit.py <this folder>`.
"""

PROOF_CONTEXT = """# CONTEXT — Proof

**Where am I?** Proving the `{skill}` retrofit.

**What am I proving?** Two things, and a retrofit that fails either is not
finished.

1. **It routes.** Three different phrasings of the same intent, none of them
   the phrasing the description was written for. All three must return
   `{skill}` at position 1.

       omnicli search "<phrasing one>"
       omnicli search "<phrasing two>"
       omnicli search "<phrasing three>"

   One phrasing proves nothing. Three phrasings prove the skill is
   discoverable by intent rather than by memorised wording.

2. **Nothing else broke.** Routing is shared. A change that lifts this skill
   by demoting another is a regression.

       omnicli eval

   Compare against the baseline. Top-1 must not fall.

**What if the proof fails?** Fix the skill, not the proof. If the skill
genuinely cannot win a phrasing it should have won, the alias set is the
thing to change — not the description, and never the other skills.
"""


def find_skill(name: str) -> Path | None:
    for root in (COLLECTION,):
        d = root / name
        if (d / "SKILL.md").is_file():
            return d
    # Fall back to a search by frontmatter name.
    for d in sorted(COLLECTION.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        try:
            head = md.read_text(encoding="utf-8", errors="replace")[:400]
        except OSError:
            continue
        if re.search(rf"^name:\s*{re.escape(name)}\s*$", head, re.MULTILINE):
            return d
    return None


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")


def current_aliases(name: str) -> dict:
    """Read the skill's current curated metadata from omnicli."""
    omnicli = shutil.which("omnicli")
    if not omnicli:
        return {}
    try:
        out = subprocess.run([omnicli, "alias", name, "--json"],
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return {}


def mine_candidates(skill_dir: Path) -> list[str]:
    """Words the body uses that the name and description do not.

    The vocabulary gap is computable: a term the body uses but the front
    matter does not is a word a user might type that the skill would fail
    to match on. A starting point for curation, not a finished alias set.
    """
    try:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    fm = m.group(1) if m else ""
    body = text[m.end():] if m else text
    known = set(re.findall(r"[a-z0-9]+", fm.lower()))
    counts: dict[str, int] = {}
    for tok in re.findall(r"[a-z][a-z0-9-]{3,}", body.lower()):
        if tok in known or tok in STOP:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [t for t, _ in ranked[:30]]


STOP = {
    "about", "after", "again", "against", "along", "also", "always", "because",
    "before", "being", "below", "between", "both", "cannot", "could", "does",
    "doing", "done", "down", "during", "each", "either", "else", "even",
    "every", "from", "further", "have", "having", "here", "however", "into",
    "itself", "just", "like", "make", "many", "more", "most", "much", "must",
    "only", "other", "over", "same", "should", "since", "some", "such",
    "than", "that", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "under", "until", "very", "were", "what", "when",
    "where", "which", "while", "with", "would", "your", "using", "used",
    "use", "need", "want", "will", "shall", "here", "http", "https",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a staged run area for a skill retrofit.")
    ap.add_argument("skill", help="Skill to retrofit")
    ap.add_argument("--template", action="store_true",
                    help="Seed an empty draft (greenfield) instead of the current skill")
    ap.add_argument("--runs", default=None, help="Override the runs root")
    args = ap.parse_args()

    runs_root = Path(args.runs) if args.runs else RUNS_ROOT
    skill_dir = find_skill(args.skill)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run = runs_root / f"{slug(args.skill)}-{stamp}"

    for stage in ("01_interview", "02_draft", "03_proof"):
        (run / stage).mkdir(parents=True, exist_ok=True)

    (run / "01_interview" / "CONTEXT.md").write_text(
        INTERVIEW_CONTEXT.format(skill=args.skill), encoding="utf-8")
    (run / "02_draft" / "CONTEXT.md").write_text(
        DRAFT_CONTEXT.format(skill=args.skill, collection=COLLECTION), encoding="utf-8")
    (run / "03_proof" / "CONTEXT.md").write_text(
        PROOF_CONTEXT.format(skill=args.skill), encoding="utf-8")

    # Seed the draft.
    if args.template or skill_dir is None:
        draft = (TEMPLATE_DIR / "02_draft" / "SKILL.md.template")
        text = draft.read_text(encoding="utf-8") if draft.is_file() else ""
        text = text.replace("{skill}", args.skill)
    else:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    (run / "02_draft" / "SKILL.md").write_text(text, encoding="utf-8")

    # Seed the alias set, with mined candidates for curation.
    rec = current_aliases(args.skill)
    candidates = mine_candidates(skill_dir) if skill_dir else []
    (run / "02_draft" / "aliases.json").write_text(json.dumps({
        "skill": args.skill,
        "aliases": rec.get("aliases", []),
        "tags": rec.get("tags", []),
        "mined_candidates": candidates,
        "_note": "Curate `aliases` by hand from the mined candidates. Keep 5-12. "
                 "The aliases are the routing surface: the words a user would type "
                 "that appear in no document.",
    }, indent=2) + "\n", encoding="utf-8")

    # The path goes on its own line, unlabelled. A "Run area: <path>" line
    # reads as one path-shaped string, and a reader that copies it verbatim
    # ends up creating a directory named "area:".
    print(f"📂 Run area\n   {run}")
    print(f"   01_interview/  read the existing skill")
    print(f"   02_draft/      write SKILL.md + aliases.json")
    print(f"   03_proof/      prove routing, check for regressions")
    if skill_dir:
        print(f"\n   source: {skill_dir}")
    print(f"\n   Next: read {run}/01_interview/CONTEXT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
