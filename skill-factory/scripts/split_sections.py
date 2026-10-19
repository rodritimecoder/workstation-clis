"""Split a skill's SKILL.md into a house-shape body plus reference files.

Used by the retrofit loop: sections that are reference material are moved
verbatim into references/, and the body is reassembled around them.

    python3 split_sections.py <skill-dir> <run-dir> "Section A=ref-a.md" ...
"""

import re
import sys
from pathlib import Path


def sections(body):
    """Return [(title, level, text)] for every H2 section."""
    out = []
    marks = list(re.finditer(r"^##\s+(.*)$", body, re.M))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((m.group(1).strip(), m.start(), body[m.start():end].rstrip() + "\n"))
    return out


def main():
    skill_dir = Path(sys.argv[1])
    run_dir = Path(sys.argv[2])
    pairs = []
    for spec in sys.argv[3:]:
        title, fname = spec.split("=", 1)
        pairs.append((title, fname))

    src = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n.*?\n---\s*\n", src, re.DOTALL)
    body = src[m.end():] if m else src

    refs = run_dir / "references"
    refs.mkdir(parents=True, exist_ok=True)

    secs = {t.strip(): text for t, _, text in sections(body)}
    for title, fname in pairs:
        text = secs.get(title)
        if text is None:
            print(f"  MISSED section: {title!r}")
            continue
        (refs / fname).write_text(text, encoding="utf-8")
        print(f"  moved {title:<46} -> {fname}  ({len(text.split())} words)")

    # keep everything else as a single blob, for hand-assembly
    (run_dir / "_remaining.md").write_text(body, encoding="utf-8")
    print(f"  remaining body: {len(body.split())} words")


if __name__ == "__main__":
    main()
