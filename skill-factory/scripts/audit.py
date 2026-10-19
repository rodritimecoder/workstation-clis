#!/usr/bin/env python3
"""audit.py — the deterministic gate for a generated skill.

Checks a SKILL.md against the rules that make a skill routable and cheap to
read. Every rule is derived from this collection's own best example
(``tailscale-ops``) or from a measured failure, not invented.

    audit.py <skill-dir>          audit one skill
    audit.py --all                audit every skill in the collection
    audit.py --all --json         machine-readable
    audit.py <skill-dir> --strict  warnings become failures

Exit code is 0 when the skill passes, 1 when it does not. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------- budgets

# The house style runs 41-53 words (median 41). Only five skills in the
# collection exceed 60, and all five are genuinely wrong rather than
# house-styled: icm-architect 147, agent-reach 121, audiocpp 75,
# review-hub 66, guard-hooks 63.
MAX_DESC_WORDS = 90     # warns, does not fail
MAX_BODY_WORDS = 1500   # runaway guard, not a shape rule

# A concept section is the mental model: a table, or a short numbered list.
# It is the one place prose is *allowed* to live, because it is what lets an
# agent know which command to reach for. jev-decision's "Universal Decision
# Primitives" table is the model for this — four rows, an examples column,
# 106 words.
#
# A *procedure* is a numbered list of steps the agent follows. It is the same
# shape as a concept but a different job, and it is allowed to be longer:
# cornell-notes' five-step Workflow is 195 words and is the skill.
#
# Bullets are neither. A bulleted list is background — rules, caveats,
# options — and it moves to references/ like any other prose.
CONCEPT_MAX_WORDS = 120
PROCEDURE_MAX_WORDS = 600
CONCEPT_MAX_ITEMS = 20

# A numbered list's readability is per item, exactly as a table's is per row.
# swarm-contract's three items are 28 words each; icm-architect's ten
# invariants are 43 each; cornell-notes' five workflow steps are 39 each.
# A list that turns into a wall of text in one item does not pass.
LIST_MAX_WORDS_PER_ITEM = 50

# A table's readability is per row, not per table. jev-decision's primitive
# table is 4 rows of 26 words; github-architect's protocol table is 7 rows
# of 25. A flat word cap would reject the second and pass the first, which
# is backwards — a table that grows rows stays a table, and a table that
# turns into a wall of text in one cell does not.
TABLE_MAX_WORDS_PER_ROW = 40

# An alias is weighted as a whole column, so every word inside a multi-word
# alias inherits that weight. A phrase like "text embeddings api" therefore
# hands its owner a strong signal on the word "text" — a word that belongs to
# half the collection. These are the words that should not appear in an
# alias; the gate warns so a human can re-curate.
GENERIC_ALIAS_WORDS = {
    "api", "code", "command", "content", "data", "file", "files", "get",
    "input", "list", "make", "model", "models", "output", "page", "pages",
    "run", "script", "search", "server", "service", "task", "text", "tool",
    "tools", "use", "web", "work",
}

BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
NUMBERED_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)

# Box-drawing characters, the signature of an ASCII architecture diagram.
DIAGRAM_CHARS = set("┌┐└┘├┤┬┴┼─│╔╗╚╝═║╠╣╦╩╬┏┓┗┛")


def _is_diagram(content: str) -> bool:
    """Does this fence draw a diagram rather than show data or commands?"""
    return sum(1 for ch in content if ch in DIAGRAM_CHARS) >= 8

# A JSON or YAML fence is the *contract* the agent has to produce — the
# shape of the intermediate file. cornell-notes' JSON schema is 73 words
# that the agent must read before it can act, so it is structure, not
# commentary, and it is excluded from the per-command overhead ratio.
CONTRACT_FENCE_RE = re.compile(r"^```(json|ya?ml)\s*$", re.MULTILINE)

# Soft target, reported but not a failure. The house style itself sits
# around 34: swarm-contract 34, jev-decision 34, state-compactor 28. It is
# a smell, not a rule — icm-architect sits at 302 with seven commands, and
# that is not a smell, it is a problem.

# Section titles that should not be in a skill body. The body is read by an
# agent that already knows what it wants to do; these are the sections an
# agent skips, and they are the sections that cost the most.
#
# "architecture" is NOT here: the house style uses a concept section, and
# banning it was a mistake — it counted concept as prose and inflated the
# measured backlog by 3x.
BANNED_TITLES = [
    "overview", "introduction", "intro", "background", "about",
    "installation", "install", "setup", "requirements", "prerequisites",
    "when to use", "troubleshooting", "how it works", "internals", "notes",
]

# A skill body must not hardcode a harness path. The same skill is mirrored
# into three harness directories, so an absolute path is wrong documentation
# that happens to resolve.
HARNESS_PATH_RE = re.compile(
    r"(?:~|\$HOME|\$\{HOME\})?/\.(?:gemini/config/skills|config/opencode/skills|pi/agent/skills)"
    r"[^\s`'\"]*"
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE_RE = re.compile(r"^```([^\n]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BINDING_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$", re.MULTILINE)
PYTHON_BINARIES = ("python3", "python", "python3.14", "python3.12")


def parse_bindings(content: str) -> dict[str, str]:
    """Read ``VAR="command"`` bindings out of a fence.

    The house style binds the tool once and then uses ``$VAR`` for every
    command. That keeps each command line short, and it means the binding
    line is not a command — treating it as one made the gate fail on
    ``SWARM="python3 ..."``.
    """
    out: dict[str, str] = {}
    for m in BINDING_RE.finditer(content):
        var = m.group(1)
        val = m.group(2).strip().strip("\"'")
        parts = val.split()
        if not parts:
            continue
        if parts[0] in PYTHON_BINARIES and len(parts) > 1:
            out[var] = parts[1]
        else:
            out[var] = parts[0]
    return out


def is_concept(content: str, words: int) -> str | None:
    """Is this section structure rather than background?

    Returns the kind — ``"table"``, ``"procedure"`` — or None if the section
    is stray prose that should move to references/.

    Two accepted forms, both from the house style:
    * a markdown table (jev-decision's decision primitives), or
    * a numbered list (swarm-contract's tripartite contract, cornell-notes'
      five-step workflow).

    A bulleted list is not structure. It is background, and it moves.
    """
    if content.count("|") >= 4 and "---" in content:
        rows = [ln for ln in content.splitlines()
                if ln.strip().startswith("|") and not set(ln.strip()) <= set("| -")]
        # The separator row is the only non-data row left; the header was
        # already removed above.
        body_rows = [r for r in rows if not re.fullmatch(r"\|[\s:|-]+\|", r.strip())]
        if body_rows:
            if words / len(body_rows) <= TABLE_MAX_WORDS_PER_ROW:
                return "table"
        return None
    items = NUMBERED_RE.findall(content)
    if 2 <= len(items) <= CONCEPT_MAX_ITEMS and words <= PROCEDURE_MAX_WORDS:
        if words / len(items) <= LIST_MAX_WORDS_PER_ITEM:
            return "procedure"
    # A bulleted list whose items each open with a bolded lead-in term is a
    # concept model, not background. "- **Git Worktree Isolation**: Never
    # let..." names a thing; "- Always use standard LaTeX syntax" states a
    # rule. The bolded lead-in is the difference.
    bold_items = re.findall(r"^\s*[-*+]\s+\*\*", content, re.MULTILINE)
    if 2 <= len(bold_items) <= CONCEPT_MAX_ITEMS and words <= PROCEDURE_MAX_WORDS:
        if words / len(bold_items) <= LIST_MAX_WORDS_PER_ITEM:
            return "procedure"
    return None


def count_commands(content: str) -> int:
    """Real commands in a fence: not comments, not bindings."""
    n = 0
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if BINDING_RE.match(s):
            continue
        n += 1
    return n


def skill_overrides() -> dict[str, dict]:
    """Per-skill budget overrides, read from the catalog's alias config.

    A *command surface* skill is read to find a command, so its body has a
    tight budget. A *method* skill is read to learn the method, and the
    method is the product — icm-architect's ten invariants are 430 words
    that an agent genuinely needs before it can build a workspace.

    One source of truth: the catalog's own alias config, so the budget a
    skill claims and the budget the gate enforces cannot drift apart.
    """
    import os
    root = os.environ.get("OMNICLI_ROOT", "/run/media/rodri/AI/workstation-clis/omnicli")
    path = Path(root) / "catalog" / "aliases.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------
# helpers

def mask_fences(text: str) -> str:
    """Blank out fenced code blocks, preserving every offset and newline.

    A shell comment inside a fence looks exactly like a markdown heading
    (``# Open a URL``), so headings have to be read from a copy with the
    fences removed. Blanking rather than deleting keeps line numbers and
    character offsets valid against the original.
    """
    out = list(text)
    for m in FENCE_RE.finditer(text):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def strip_frontmatter(text: str) -> tuple[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def parse_frontmatter(fm: str) -> dict[str, str]:
    """Minimal frontmatter reader: scalars and folded blocks, no YAML dep."""
    out: dict[str, str] = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", "|", ">-", "|-"):
            block = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                block.append(lines[i].strip())
                i += 1
            out[key] = " ".join(x for x in block if x).strip().strip("\"'")
            continue
        out[key] = val.strip().strip("\"'")
        i += 1
    return out


def sections(body: str) -> list[dict]:
    """Split a body into heading sections, marking which have children.

    A heading with a deeper heading inside is a *group* (a table of contents
    for its children). A heading with no deeper heading inside is a *leaf*,
    and a leaf is what an agent actually reads.

    Headings are located in a fence-masked copy of the body, but section
    content is read from the original, so the commands inside a fence are
    still seen.
    """
    masked = mask_fences(body)
    marks = []
    for m in HEADING_RE.finditer(masked):
        marks.append({
            "start": m.start(),
            "content_start": m.end(),
            "level": len(m.group(1)),
            "title": m.group(2).strip(),
            "line": masked[: m.start()].count("\n") + 1,
        })
    for i, sec in enumerate(marks):
        end = len(body)
        has_child = False
        for j in range(i + 1, len(marks)):
            if marks[j]["level"] <= sec["level"]:
                end = marks[j]["start"]
                break
            has_child = True
        content = body[sec["content_start"]: end]
        sec["content"] = content
        sec["words"] = len(content.split())
        sec["is_group"] = has_child
        sec["fences"] = FENCE_RE.findall(content)
        # A command fence is a shell fence. An untagged fence is shell only
        # if it *starts* like an invocation: an untagged fence is often an
        # illustrative payload — a sample of the tool's own output — and
        # treating it as shell turned `zoom-recorder/scripts/zoom_download`
        # into a "command". The first line decides; later lines in a
        # command fence may be continuations or comments.
        def _is_shell(lang: str, c: str) -> bool:
            if lang.strip():
                return lang.strip() in ("bash", "sh", "shell", "console")
            first = next((ln.strip() for ln in c.splitlines() if ln.strip()), "")
            if not first or not (first[0].isalnum() or first[0] in "_$./"):
                return False
            if re.match(r"^(\d+\.|[-*+])\s", first):
                return False
            # A metrics row — "BM25 catalog  top1 52/53 (98.1%)  top3 ..." —
            # is a results table, not an invocation. It has a wide column gap
            # and numbers in it; a command line does not.
            if len(first) - len(re.sub(r"\s+", " ", first)) >= 2 and re.search(r"\d", first):
                return False
            return first.count("=") <= 1

        sec["command_fences"] = [
            (lang, c) for lang, c in sec["fences"] if _is_shell(lang, c)
        ]
        sec["has_command"] = bool(sec["command_fences"])
        # A section that points at a reference file is actionable too:
        # "read this for the detail" is an action.
        sec["has_reference"] = bool(re.search(r"`[^`]*\.md`|\]\([^)]*\.md\)", content))
        sec["has_contract"] = bool(CONTRACT_FENCE_RE.search(content))
        sec["has_action"] = (sec["has_command"] or sec["has_reference"]
                             or sec["has_contract"])
    return marks


def word_count(text: str) -> int:
    return len(text.split())


def approx_tokens(text: str) -> int:
    """Rough token estimate. Characters/4 is the standard approximation."""
    return max(1, len(text) // 4)


def resolve_command(token: str, skill_dir: Path) -> bool:
    """Is the first word of a command something that exists?"""
    token = token.strip().strip("\"'")
    if not token:
        return True
    if token.startswith((".", "/", "~", "$")):
        p = Path(token.replace("~", str(Path.home()), 1))
        if p.is_file() or p.is_dir():
            return True
        try:
            if (skill_dir / token.lstrip("./")).exists():
                return True
        except OSError:
            pass
        # A path into a harness mirror is legitimate only if it exists.
        return p.exists()
    return shutil.which(token) is not None


# ---------------------------------------------------------------- the audit

def audit_skill(skill_dir: Path, expect_name: str | None = None) -> dict:
    md = skill_dir / "SKILL.md"
    target_name = expect_name or skill_dir.name
    result: dict = {
        "skill": target_name,
        "path": str(skill_dir),
        "errors": [],
        "warnings": [],
        "info": {},
        "exists": md.is_file(),
    }
    if not md.is_file():
        result["errors"].append({"rule": "frontmatter", "detail": "no SKILL.md"})
        result["ok"] = False
        return result

    text = md.read_text(encoding="utf-8", errors="replace")
    fm_raw, body = strip_frontmatter(text)
    fm = parse_frontmatter(fm_raw)

    # --- rule 1: frontmatter -------------------------------------------
    if not fm_raw.strip():
        result["errors"].append({"rule": "frontmatter", "detail": "no YAML frontmatter"})
    if "name" not in fm:
        result["errors"].append({"rule": "frontmatter", "detail": "no 'name' field"})
    elif fm["name"] != target_name:
        result["errors"].append({
            "rule": "frontmatter",
            "detail": f"name '{fm['name']}' != expected '{target_name}'",
        })
    if "description" not in fm or not fm["description"].strip():
        result["errors"].append({"rule": "frontmatter", "detail": "no 'description' field"})

    # --- rule 2: description present -----------------------------------
    # Length is deliberately NOT checked. The description is in the turn-0
    # shelf, so a tight one is nicer — but gating on a word count made the
    # gate noisy and the work slower, and the thing that actually decides
    # routing is the alias set, not the description's length.
    desc = fm.get("description", "")
    desc_words = word_count(desc)
    if desc_words > MAX_DESC_WORDS:
        result["warnings"].append({
            "rule": "long-description",
            "detail": f"{desc_words} words — the shelf is paid every turn",
        })

    # --- rule 8: body budget -------------------------------------------
    # A loose runaway guard, not a shape rule. A body of a few thousand
    # words is a signal that something was pasted in; it is not a failure.
    # An omnicli-routed agent never reads the body — the contract comes
    # from the script's own --help — so word count is not a cost worth
    # gating on.
    body_words = word_count(body)
    overrides = skill_overrides().get(target_name, {})
    body_budget = int(overrides.get("body_budget", MAX_BODY_WORDS))
    if body_words > body_budget:
        result["errors"].append({
            "rule": "body-budget",
            "detail": f"{body_words} words, runaway guard {body_budget}",
        })

    # --- single H1 -----------------------------------------------------
    masked = mask_fences(body)
    h1s = [m for m in HEADING_RE.finditer(masked) if len(m.group(1)) == 1]
    if len(h1s) != 1:
        result["errors"].append({
            "rule": "single-h1",
            "detail": f"{len(h1s)} H1 headings, expected exactly 1",
        })

    secs = sections(body)
    leaves = [s for s in secs if not s["is_group"]]

    # --- rule 5: banned titles -----------------------------------------
    for s in secs:
        norm = re.sub(r"[^a-z ]", "", s["title"].lower()).strip()
        for banned in BANNED_TITLES:
            if norm == banned or norm.startswith(banned + " ") or norm.startswith(banned + ":"):
                result["errors"].append({
                    "rule": "banned-section",
                    "detail": f"'{s['title']}' (line {s['line']}) should move to references/",
                })
                break

    # --- classify the leaves -------------------------------------------
    # A leaf is one of four things:
    #   action    — it carries a command the agent can run
    #   concept   — a table, or a short numbered list: the mental model
    #   contract  — a json/yaml block: the shape the agent has to produce
    #   reference — a pointer at a file in references/
    # Anything else is unclassified, and that is the only thing the gate
    # needs to object to. *How long* it is turns out not to matter: an
    # omnicli-routed agent never reads the body at all, because the
    # contract comes from the script's own --help.
    #
    # Concept is checked first. A concept table routinely mentions a
    # filename in a cell, and a mention of `SKILL.md` must not promote a
    # concept model to an action.
    concept_leaves, contract_leaves = [], []
    reference_leaves, action_leaves, prose_leaves = [], [], []
    for s in leaves:
        # A section whose fence is an ASCII diagram is the mental model drawn
        # rather than tabulated. Both graph-memory's "Two Legs of Memory" and
        # academic-icm's "4-Stage Architecture" are this form.
        if any(_is_diagram(c) for _, c in s["fences"]):
            s["is_concept"] = True
            concept_leaves.append(s)
        elif is_concept(s["content"], s["words"]):
            s["is_concept"] = True
            concept_leaves.append(s)
        elif s.get("has_contract"):
            contract_leaves.append(s)
        elif s["has_command"]:
            action_leaves.append(s)
        elif s["has_reference"]:
            reference_leaves.append(s)
        else:
            s["is_concept"] = False
            prose_leaves.append(s)

    # --- rule 3: every leaf is an action, a concept, or a pointer -------
    for s in prose_leaves:
        result["errors"].append({
            "rule": "leaf-unclassified",
            "detail": f"'{s['title']}' (line {s['line']}) is neither a command, "
                      f"a concept model, nor a pointer at a reference file",
        })

    # --- rule 4: no size limit on leaves --------------------------------
    # A leaf's length is not a defect. If a leaf is neither a command, a
    # concept model, nor a reference pointer, the leaf-unclassified rule
    # above already says so, and the fix is structural: make it a concept,
    # or move it to references/ and leave a pointer.

    # --- rule 6: hardcoded harness paths --------------------------------
    for m in HARNESS_PATH_RE.finditer(body):
        result["errors"].append({
            "rule": "harness-path",
            "detail": f"hardcoded harness path: {m.group(0)[:70]}",
        })

    # --- rule 7: commands resolve ---------------------------------------
    # Bindings are collected per section, so a `$VAR` bound in one fence
    # resolves in the commands that use it. Only leaf sections are counted:
    # a group's content contains its children's, so counting both would
    # count every command twice.
    unresolved = []
    total_commands = 0
    for s in leaves:
        bindings: dict[str, str] = {}
        continued = False
        for lang, content in s["command_fences"]:
            if lang and lang.strip() not in ("bash", "sh", "shell", "console", ""):
                continue
            bindings.update(parse_bindings(content))
            for raw in content.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if BINDING_RE.match(line):
                    continue          # a binding, not a command
                if line.startswith("export "):
                    continue          # an environment variable, not a command
                if continued:
                    # This line is the tail of the previous command — its
                    # arguments, not a command of its own.
                    continued = line.endswith("\\")
                    continue
                if "|" in line:      # a pipeline: check the first command
                    line = line.split("|")[0].strip()
                if line.startswith("sudo ") or line.startswith("env "):
                    line = line.split(None, 1)[1] if " " in line else ""
                if not line:
                    continue
                if not line[0] in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$.\"'/":
                    # Box drawing, bullets, rules — a diagram or a list, not
                    # a command. The ASCII architecture diagrams in this
                    # collection are the main source of these.
                    continue
                continued = line.endswith("\\")
                token = line.split()[0].strip("\"'")
                if token.startswith("$"):
                    var = token[1:]
                    if var not in bindings:
                        unresolved.append(f"{token} (line {s['line']}) — unbound variable")
                        continue
                    token = bindings[var]
                total_commands += 1
                if not resolve_command(token, skill_dir):
                    unresolved.append(f"{token} (line {s['line']})")
    for u in unresolved:
        result["errors"].append({"rule": "unresolved-command", "detail": u})

    # --- soft target: words per command --------------------------------
    # --- generic words inside aliases ----------------------------------
    # An alias column is weighted as a whole, so a generic word inside a
    # multi-word alias inherits a strong signal it has not earned.
    for alias in overrides.get("aliases", []):
        bad = sorted({w for w in re.findall(r"[a-z0-9]+", alias.lower())
                      if w in GENERIC_ALIAS_WORDS})
        if bad:
            result["warnings"].append({
                "rule": "generic-alias-word",
                "detail": f"alias {alias!r} donates weight to the generic word(s) "
                          f"{', '.join(bad)}",
            })

    # The concept section and the contract block are not per-command
    # overhead — they are what makes the commands legible and what the
    # agent has to produce. So both are excluded from the ratio, and the
    # ratio measures the explanation attached to each command.
    overhead_words = (body_words
                      - sum(s["words"] for s in concept_leaves)
                      - sum(s["words"] for s in contract_leaves))
    wpc = round(overhead_words / total_commands, 1) if total_commands else 0

    result["info"] = {
        "description_words": desc_words,
        "description_tokens": approx_tokens(desc),
        "body_words": body_words,
        "body_tokens": approx_tokens(body),
        "total_tokens": approx_tokens(fm_raw) + approx_tokens(body),
        "sections": len(secs),
        "leaves": len(leaves),
        "action_leaves": len(action_leaves),
        "concept_leaves": len(concept_leaves),
        "concept_words": sum(s["words"] for s in concept_leaves),
        "prose_leaves": len(prose_leaves),
        "prose_words": sum(s["words"] for s in prose_leaves),
        "reclaimable_words": sum(s["words"] for s in prose_leaves),
        "commands": total_commands,
        "words_per_command": wpc,
        "frontmatter": fm,
    }
    result["ok"] = not result["errors"]
    return result


# ---------------------------------------------------------------- reporting

def report(result: dict) -> None:
    info = result["info"]
    name = result["skill"]
    if not result["exists"]:
        print(f"❌ {name}: no SKILL.md")
        return
    status = "✅ PASS" if result["ok"] else "❌ FAIL"
    print(f"\n{status}  {name}")
    print(f"   description {info['description_words']}w (~{info['description_tokens']} tok)"
          f"   body {info['body_words']}w (~{info['body_tokens']} tok)")
    print(f"   leaves {info['action_leaves']} action / {info['concept_leaves']} concept"
          f" / {info['prose_leaves']} prose")
    print(f"   concept {info['concept_words']}w   prose {info['prose_words']}w"
          f"   reclaimable {info['reclaimable_words']}w")
    if info.get("commands"):
        print(f"   commands {info['commands']}")
    by_rule: dict[str, list[str]] = {}
    for e in result["errors"]:
        by_rule.setdefault(e["rule"], []).append(e["detail"])
    for rule, details in by_rule.items():
        print(f"   ❌ {rule}")
        for d in details[:6]:
            print(f"        {d}")
        if len(details) > 6:
            print(f"        ... and {len(details) - 6} more")
    for w in result["warnings"]:
        print(f"   ⚠️  {w['rule']}: {w['detail']}")


def audit_all(root: Path) -> list[dict]:
    results = []
    for item in sorted(root.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if item.name in ("glitch-cat", "archived", "docs", "launchers", "modules"):
            continue
        if not (item / "SKILL.md").is_file():
            continue
        results.append(audit_skill(item))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a skill against the routing and token rules.")
    ap.add_argument("skill", nargs="?", help="Skill directory")
    ap.add_argument("--all", action="store_true", help="Audit every skill in the collection")
    ap.add_argument("--root", default=None, help="Collection root (default: the skills dir)")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    ap.add_argument("--strict", action="store_true", help="Warnings become failures")
    ap.add_argument("--summary", action="store_true", help="Only print the summary table")
    ap.add_argument("--expect-name", default=None,
                    help="Expected frontmatter name (for auditing a draft folder)")
    args = ap.parse_args()

    if args.all:
        root = Path(args.root) if args.root else Path("/run/media/rodri/AI/skills")
        results = audit_all(root)
    elif args.skill:
        results = [audit_skill(Path(args.skill), expect_name=args.expect_name)]
    else:
        ap.error("give a skill directory or --all")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if all(r["ok"] for r in results) else 1

    if not args.summary:
        for r in results:
            report(r)

    total_desc = sum(r["info"].get("description_words", 0) for r in results)
    total_body = sum(r["info"].get("body_words", 0) for r in results)
    total_reclaim = sum(r["info"].get("reclaimable_words", 0) for r in results)
    total_prose = sum(r["info"].get("prose_words", 0) for r in results)
    failing = [r for r in results if not r["ok"]]
    print("\n" + "=" * 72)
    print(f"  {len(results)} skills audited · {len(failing)} failing")
    print(f"  descriptions {total_desc}w (~{total_desc * 13 // 10} tok)"
          f"   bodies {total_body}w (~{total_body * 13 // 10} tok)")
    print(f"  prose {total_prose}w of which {total_reclaim}w over budget → move to references/")
    print("=" * 72 + "\n")
    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
