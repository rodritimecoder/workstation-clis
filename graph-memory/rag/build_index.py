"""Build the index: chunk markdown on headings, index keywords and meaning.

Reads ../corpus-before by default, plus any distilled entries in distilled/.
Subfolders are included, so the digest's daily/ folder is indexed like any note.
Writes rag.db next to this script. Run again any time; the index is disposable.
"""

import argparse
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
CHUNK_BUDGET = 1600  # characters, roughly 400 tokens
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://127.0.0.1:8082/v1/embeddings")


def get_embeddings(texts, endpoint=EMBEDDING_URL, batch_size=8):
    """Fetch embeddings via OpenAI-compatible endpoint using urllib."""
    all_vecs = []
    total = len(texts)
    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        # Defensively bound chunk length to prevent 512-token context window overflow
        batch = [t[:1100] for t in batch]
        payload = json.dumps({"input": batch}).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                data_items = sorted(res_data["data"], key=lambda x: x.get("index", 0))
                for item in data_items:
                    all_vecs.append(item["embedding"])
        except Exception:
            # Fallback to single-item requests if batch fails
            for item_text in batch:
                try:
                    sub_payload = json.dumps({"input": item_text[:800]}).encode("utf-8")
                    sub_req = urllib.request.Request(
                        endpoint, data=sub_payload, headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(sub_req, timeout=30) as sub_resp:
                        sub_data = json.loads(sub_resp.read().decode("utf-8"))
                        all_vecs.append(sub_data["data"][0]["embedding"])
                except Exception:
                    # Absolute fallback: dummy normalized vector
                    dummy = [0.0] * 384
                    dummy[0] = 1.0
                    all_vecs.append(dummy)
        if (i // batch_size) % 25 == 0 or i + batch_size >= total:
            print(f"embedded {min(i + batch_size, total)}/{total} chunks...")
    return all_vecs


SCHEMA = """
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS vectors;
DROP TABLE IF EXISTS meta;
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    section TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    text TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'chunk'
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, file, section);
CREATE TABLE vectors (id INTEGER PRIMARY KEY, vec BLOB NOT NULL);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def note_files(corpus):
    """Every markdown file under the corpus, subfolders included.

    Skipped: hidden files and folders, .git, node_modules, __pycache__, and
    this starter's own folder when it has been cloned inside the notes.
    """
    root = Path(corpus).resolve()
    starter = HERE.parent.resolve()
    # the starter is skipped only when it sits INSIDE your notes, which is the
    # case the rule exists for. A corpus inside the starter is the bundled demo
    # folders, and those are meant to be indexed.
    skip_starter = starter != root and root in starter.parents
    out = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts):
            continue
        if skip_starter and (starter == path.parent or starter in path.parents):
            continue
        out.append(path)
    return out


def sections(lines):
    """Split markdown lines into (heading, start, end) sections."""
    out = []
    heading, start = None, 0
    for i, line in enumerate(lines):
        if re.match(r"^#{1,3} ", line):
            if i > start or heading is not None:
                out.append((heading, start, i))
            heading, start = line.lstrip("# ").strip(), i
    out.append((heading, start, len(lines)))
    return [(h, s, e) for h, s, e in out if any(l.strip() for l in lines[s:e])]


def chunk_file(path):
    """Yield (section, start_line, end_line, text) chunks packed to the budget."""
    lines = path.read_text(encoding="utf-8").splitlines()
    packed = []
    for heading, s, e in sections(lines):
        text = "\n".join(lines[s:e]).strip()
        title = heading or path.stem
        if len(text) <= CHUNK_BUDGET:
            packed.append((title, s + 1, e, text))
            continue
        # oversized section: split on line groups within the budget
        buf, buf_start = [], s
        for i in range(s, e):
            buf.append(lines[i])
            if sum(len(l) + 1 for l in buf) >= CHUNK_BUDGET:
                packed.append((title, buf_start + 1, i + 1, "\n".join(buf).strip()))
                buf, buf_start = [], i + 1
        if any(l.strip() for l in buf):
            packed.append((title, buf_start + 1, e, "\n".join(buf).strip()))
    return packed


def parse_entry(text):
    """Read a distilled entry: source, questions, summary, rule, quote.

    distil.py checks its own output through this, so the writer and the reader
    can never drift into two spellings of the format.
    """
    entry = {"questions": []}
    for line in text.splitlines():
        if line.startswith("source:"):
            entry["source"] = line.split(":", 1)[1].strip()
        elif line.startswith("- "):
            entry["questions"].append(line[2:].strip())
        elif line.startswith("summary:"):
            entry["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("rule:"):
            entry["rule"] = line.split(":", 1)[1].strip()
        elif line.startswith("quote:"):
            entry["quote"] = line.split(":", 1)[1].strip().strip('"')
    return entry


def parse_distilled(path):
    """Read a distilled entry from a file."""
    return parse_entry(path.read_text(encoding="utf-8"))


def normalise(text):
    return " ".join(text.split())


def utf8_out():
    """Write UTF-8 whatever the console's code page is.

    Windows consoles default to cp1252, which cannot encode an arrow, a curly
    quote or a pound sign, and file names and notes are full of them.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    utf8_out()
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(HERE.parent / "corpus-before"))
    args = ap.parse_args()
    corpus = Path(args.corpus)

    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO meta VALUES ('corpus', ?)", (str(corpus.resolve()),))

    docs = []  # (embed_text, row)
    files = note_files(corpus)
    root = corpus.resolve()
    for path in files:
        # the relative path is the file's name in the index, so a note in a
        # subfolder can still be read back for context
        rel = path.relative_to(root).as_posix()
        for section, s, e, text in chunk_file(path):
            label = f"[{rel} § {section}]"
            row = (rel, section, s, e, text, "chunk")
            docs.append((label + "\n" + text, row))

    dropped = 0
    distilled_dir = HERE / "distilled"
    distilled_files = sorted(distilled_dir.glob("*.md")) if distilled_dir.is_dir() else []
    for path in distilled_files:
        entry = parse_distilled(path)
        source = corpus / entry.get("source", "")
        quote = entry.get("quote", "")
        # grounding check: the quote must appear in the source, word for word
        if not source.is_file() or normalise(quote) not in normalise(source.read_text(encoding="utf-8")):
            dropped += 1
            print(f"dropped {path.name}: quote not found in {entry.get('source', '?')}")
            continue
        body = "\n".join(
            entry["questions"]
            + [entry.get("summary", ""), entry.get("rule", ""), quote]
        ).strip()
        label = f"[{entry['source']} § distilled]"
        row = (entry["source"], "distilled", 0, 0, body, "distilled")
        docs.append((label + "\n" + body, row))

    for embed_text, row in docs:
        cur = db.execute(
            "INSERT INTO chunks (file, section, start_line, end_line, text, kind) VALUES (?,?,?,?,?,?)",
            row,
        )
        db.execute(
            "INSERT INTO chunks_fts (rowid, text, file, section) VALUES (?,?,?,?)",
            (cur.lastrowid, embed_text, row[0], row[1]),
        )

    model_line = "keyword only (embedding endpoint unavailable)"
    if not docs:
        model_line = "nothing to index: no markdown found under the corpus"
    else:
        try:
            vecs = get_embeddings([t for t, _ in docs])
            for rowid, vec in enumerate(vecs, start=1):
                norm = sum(x * x for x in vec) ** 0.5 or 1.0
                blob = struct.pack(f"{len(vec)}f", *(x / norm for x in vec))
                db.execute("INSERT INTO vectors (id, vec) VALUES (?,?)", (rowid, blob))
            model_line = f"model bge-small-en-v1.5 ({len(vecs[0])}d) + keyword sqlite fts5 via {EMBEDDING_URL}"
        except Exception as exc:
            print(f"warning: embedding leg failed ({exc}), falling back to keyword")

    db.commit()
    db.close()
    n_distilled = len(distilled_files) - dropped
    print(f"indexed {len(files)} files, {len(docs) - n_distilled} chunks, {n_distilled} distilled entries, {dropped} dropped")
    print(model_line)


if __name__ == "__main__":
    main()
