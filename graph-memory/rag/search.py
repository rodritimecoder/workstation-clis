"""Search the index: keyword leg + meaning leg, merged with rank fusion.

Usage: python search.py "your question"
Prints the top hits with the lines around them, and which leg found each.
"""

import json
import os
import re
import sqlite3
import struct
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "rag.db"
K = 60  # rank fusion smoothing constant
TOP = 3
CONTEXT_LINES = 6
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://127.0.0.1:8082/v1/embeddings")


STOPWORDS = {
    "a", "an", "and", "are", "at", "can", "do", "does", "for", "how", "i",
    "in", "is", "it", "my", "of", "on", "or", "our", "the", "to", "we",
    "what", "when", "where", "who", "why", "with", "you", "your",
}


def keyword_leg(db, query):
    terms = [t for t in re.findall(r"\w+", query.lower()) if t not in STOPWORDS]
    if not terms:
        return []
    match = " OR ".join(f'"{t}"' for t in terms)
    rows = db.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT 10",
        (match,),
    ).fetchall()
    return [r[0] for r in rows]


def meaning_leg(db, query):
    rows = db.execute("SELECT id, vec FROM vectors").fetchall()
    if not rows:
        return None
    try:
        payload = json.dumps({"input": query}).encode("utf-8")
        req = urllib.request.Request(
            EMBEDDING_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            q = res_data["data"][0]["embedding"]
    except Exception as exc:
        print(f"warning: embedding leg failed ({exc})")
        return None

    qnorm = sum(x * x for x in q) ** 0.5 or 1.0
    q = [x / qnorm for x in q]
    scored = []
    for rowid, blob in rows:
        vec = struct.unpack(f"{len(blob) // 4}f", blob)
        scored.append((sum(a * b for a, b in zip(q, vec)), rowid))
    scored.sort(reverse=True)
    return [rowid for _, rowid in scored[:10]]


def fuse(legs):
    scores, found_by = {}, {}
    for name, ids in legs.items():
        for rank, rowid in enumerate(ids):
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (K + rank)
            found_by.setdefault(rowid, []).append(name)
    ranked = sorted(scores, key=scores.get, reverse=True)
    return ranked, found_by


def show(db, rowid, position, legs):
    file, section, start, end, text, kind = db.execute(
        "SELECT file, section, start_line, end_line, text, kind FROM chunks WHERE id=?",
        (rowid,),
    ).fetchone()
    print(f"{position}. [{file} § {section}]  legs: {'+'.join(legs)}")
    out = []
    if kind == "distilled":
        out = text.splitlines()
    else:
        corpus = db.execute("SELECT value FROM meta WHERE key='corpus'").fetchone()
        source = Path(corpus[0]) / file if corpus else HERE.parent / "corpus-before" / file
        if source.is_file():
            lines = source.read_text(encoding="utf-8").splitlines()
            s = max(0, start - 1 - CONTEXT_LINES)
            e = min(len(lines), end + CONTEXT_LINES)
            # context lines wear a dot; the chunk itself is bare
            out = ["· " + l for l in lines[s : start - 1]]
            out += lines[start - 1 : end]
            out += ["· " + l for l in lines[end:e]]
        else:
            out = text.splitlines()
    print("\n".join("   " + l for l in out).rstrip())
    print()


def utf8_out():
    """Write UTF-8 whatever the console's code page is.

    Windows consoles default to cp1252, which cannot encode an arrow, a curly
    quote or a pound sign, and notes are full of them.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    utf8_out()
    if len(sys.argv) < 2:
        sys.exit('usage: python search.py "your question"')
    query = " ".join(sys.argv[1:])
    if not DB.is_file():
        sys.exit("no index yet: run python build_index.py first")
    db = sqlite3.connect(DB)

    legs = {"keyword": keyword_leg(db, query)}
    meaning = meaning_leg(db, query)
    if meaning is None:
        print(f"meaning leg off (endpoint {EMBEDDING_URL} unavailable), keyword only\n")
    else:
        legs["meaning"] = meaning

    ranked, found_by = fuse(legs)
    if not ranked:
        print("no matches")
        return
    for position, rowid in enumerate(ranked[:TOP], start=1):
        show(db, rowid, position, found_by[rowid])


if __name__ == "__main__":
    main()
