"""Retrieval for the omnicli catalog.

Two-tier design, in this order on purpose:

    BM25 (recall)  →  top-N candidates
          ↓
    embed (re-rank) →  top-N reordered to top-K      [optional, may be absent]

**Why the re-ranker is not a parallel leg.** A parallel semantic leg competes
with the lexical one, and this corpus is full of generic meta-docs
(``icm-architect``, ``review-hub``) that are semantically close to almost any
question. A parallel leg would promote them for exactly the reason the old
substring scorer did — length and genericity winning. Chaining instead means
the embedding model can only *reorder* what BM25 already surfaced. When the
embedding endpoint is down, ranking gets worse but the result set does not.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import struct
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import textutil

# FTS5 column weights. Columns are (skill, kind, title, path, body, aliases);
# the first two are UNINDEXED and must still be counted.
#
# The alias column is weighted far above prose. A curated alias is the skill
# author stating "this vocabulary routes here"; incidental body text matching
# the same word says much less. Without this separation, a large generic
# document out-votes a precise curated signal purely on volume.
TITLE_WEIGHT = 5.0
BODY_WEIGHT = 1.0
ALIAS_WEIGHT = 12.0

CANDIDATE_POOL = 200     # chunks pulled from FTS5
DEFAULT_LIMIT = 6

STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "but", "by", "can", "did",
    "do", "does", "for", "from", "get", "has", "have", "how", "i", "if", "in",
    "is", "it", "its", "me", "my", "need", "of", "on", "or", "our", "please",
    "should", "so", "some", "that", "the", "their", "then", "there", "these",
    "they", "this", "to", "tool", "use", "want", "was", "we", "what", "when",
    "where", "which", "who", "why", "will", "with", "you", "your",
}

EMBEDDING_URL = os.environ.get(
    "OMNICLI_EMBEDDING_URL", "http://127.0.0.1:8087/v1/embeddings"
)
EMBEDDING_MODEL = os.environ.get("OMNICLI_EMBEDDING_MODEL", "bge-small-en-v1.5")

# A re-ranker is only worth its latency if the endpoint is actually up.
EMBEDDING_TIMEOUT = 20.0
RERANK_CANDIDATES = 20


# --------------------------------------------------------------------------
# query construction
# --------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Query tokenizer: word tokens, with CJK runs split into bigrams."""
    return [t for t in textutil.tokenize(text) if t not in STOPWORDS]


def build_match(tokens: list[str]) -> str:
    """FTS5 MATCH expression: every token, quoted, OR-joined.

    Quoting keeps FTS5 from interpreting a token as a column filter or
    operator, which would silently drop results.
    """
    quoted = [f'"{t}"' for t in tokens if t]
    if not quoted:
        return ""
    return " OR ".join(quoted)


# --------------------------------------------------------------------------
# BM25
# --------------------------------------------------------------------------

def _bm25_leg(con: sqlite3.Connection, tokens: list[str], pool: int) -> list[sqlite3.Row]:
    """Return chunks ranked by BM25, best first.

    ``bm25()`` returns negative numbers (more negative = better match), so the
    sign is flipped to make "higher is better" hold everywhere downstream.
    """
    match = build_match(tokens)
    if not match:
        return []
    try:
        rows = con.execute(
            "SELECT d.rowid AS rid, d.skill, d.kind, d.title, d.path, d.body, "
            f"       bm25(docs, 0.0, 0.0, {TITLE_WEIGHT}, 0.0, {BODY_WEIGHT}, {ALIAS_WEIGHT}) AS raw "
            "FROM docs d WHERE docs MATCH ? "
            "ORDER BY raw LIMIT ?",
            (match, pool),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return rows


def _term_stats(con: sqlite3.Connection, tokens: list[str]) -> tuple[dict[str, int], dict[str, float]]:
    """Per-token skill-level document frequency and IDF.

    IDF is measured at the *skill* level, not the chunk level, because the
    question being asked is "which of my 27 skills should handle this?".
    A term that appears in 3 skills ("podcast") is highly discriminating; a
    term that appears in 20 ("text") barely narrows the field at all. The
    coordination factor below leans on exactly this distinction.
    """
    total = con.execute("SELECT count(DISTINCT skill) AS c FROM docs").fetchone()["c"] or 1
    df: dict[str, int] = {}
    idf: dict[str, float] = {}
    for tok in tokens:
        try:
            n = con.execute(
                "SELECT count(DISTINCT skill) AS c FROM docs WHERE docs MATCH ?", (f'"{tok}"',)
            ).fetchone()["c"]
        except sqlite3.OperationalError:
            n = 0
        df[tok] = n
        if n > 0:
            idf[tok] = math.log((total - n + 0.5) / (n + 0.5) + 1.0)
    return df, idf


def _token_hits(con: sqlite3.Connection, tokens: list[str]) -> dict[str, set[int]]:
    """Map each token to the set of doc rowids that contain it."""
    hits: dict[str, set[int]] = {}
    for tok in tokens:
        try:
            rows = con.execute(
                "SELECT rowid FROM docs WHERE docs MATCH ?", (f'"{tok}"',)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        hits[tok] = {r[0] for r in rows}
    return hits


# Coordination strength. 0 = pure BM25 (ignore which terms matched),
# 1 = a skill must cover essentially the whole query to score well.
# Tuned against tests/golden_eval.json.
COORDINATION_GAMMA = 0.65

# How many extra matching chunks a skill may count towards its coverage
# bonus. Bounded, because an uncapped bonus lets a large generic document
# accumulate score purely by having more text to match in.
COVERAGE_CAP = 4
COVERAGE_WEIGHT = 0.15

# Coordination is applied only to the top candidates by lexical score. A
# skill that is not lexically competitive cannot be rescued by covering more
# of the query, and a decisively better lexical match is not thrown away by
# an unrelated skill happening to match more generic words.
#
# Without this, "use the local llm to write a python script" went to a skill
# whose docs merely *contain* a Python example, even though the local-llm
# skill had by far the strongest lexical match.
COORDINATION_CANDIDATES = 3


def _aggregate(
    rows: list[sqlite3.Row],
    token_hits: dict[str, set[int]],
    idf: dict[str, float],
) -> list[dict[str, Any]]:
    """Collapse chunk hits into per-skill scores.

    Two factors, deliberately separated:

    * **BM25 term score** — how well the single best chunk matches.
    * **Coordination** — which *distinct* query terms the skill matched,
      weighted by IDF. A skill that matches the rare, decisive term
      ("podcast") outranks one that matches only generic terms ("turn",
      "into") even when the generic ones score higher in isolation.

    The second factor is what stops a large, generic meta-document from
    winning every query purely by having more text to match in — the exact
    failure mode of the old substring scorer, and of a parallel semantic leg.
    """
    denom = sum(idf.values())
    by_skill: dict[str, dict[str, Any]] = {}

    for r in rows:
        score = -r["raw"]  # flip: higher is better
        matched = {t for t, ids in token_hits.items() if r["rid"] in ids}
        entry = by_skill.get(r["skill"])
        if entry is None:
            entry = {"skill": r["skill"], "score": 0.0, "chunks": [], "kinds": set(), "matched": set()}
            by_skill[r["skill"]] = entry
        entry["chunks"].append({
            "kind": r["kind"],
            "title": r["title"],
            "path": r["path"],
            "score": round(score, 4),
            "matched": sorted(matched),
            "snippet": _snippet(r["body"]),
        })
        entry["kinds"].add(r["kind"])
        entry["matched"] |= matched
        if score > entry["score"]:
            entry["score"] = score

    out = []
    for entry in by_skill.values():
        n = len(entry["chunks"])
        bonus = COVERAGE_WEIGHT * min(n - 1, COVERAGE_CAP)
        lex = entry["score"] * (1.0 + bonus)

        covered = sum(idf[t] for t in entry["matched"] if t in idf)
        coordination = (covered / denom) if denom > 0 else 0.0

        entry["lexical_score"] = round(lex, 4)
        entry["coordination"] = round(coordination, 4)
        entry["matched_terms"] = sorted(entry["matched"])
        entry["coverage"] = n
        entry["kinds"] = sorted(entry["kinds"])
        entry["chunks"].sort(key=lambda c: c["score"], reverse=True)
        out.append(entry)

    # Stage 1: rank by lexical score, keep the competitive candidates.
    out.sort(key=lambda e: e["lexical_score"], reverse=True)
    head = out[:COORDINATION_CANDIDATES]
    tail = out[COORDINATION_CANDIDATES:]

    # Stage 2: coordination resolves ties among those candidates.
    for e in head:
        e["score"] = round(e["lexical_score"] * (e["coordination"] ** COORDINATION_GAMMA), 4)
    head.sort(key=lambda e: e["score"], reverse=True)

    # The tail keeps a meaningful order: it is damped by the weakest
    # coordination factor in the head, so it can never outrank a candidate
    # that was actually considered, and the score scale stays continuous.
    floor = min((e["coordination"] ** COORDINATION_GAMMA for e in head), default=0.0)
    for e in tail:
        e["score"] = round(e["lexical_score"] * floor, 4)
    tail.sort(key=lambda e: e["score"], reverse=True)

    return head + tail


def _snippet(body: str, width: int = 220) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    return text[:width] + ("…" if len(text) > width else "")


# --------------------------------------------------------------------------
# optional embedding re-ranker
# --------------------------------------------------------------------------

def _embed(texts: list[str]) -> list[list[float]] | None:
    """Call the local embedding endpoint. Returns None if it is unavailable."""
    payload = json.dumps({"input": texts, "model": EMBEDDING_MODEL}).encode("utf-8")
    req = urllib.request.Request(
        EMBEDDING_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=EMBEDDING_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    items = data.get("data")
    if not isinstance(items, list) or not items:
        return None
    try:
        return [item["embedding"] for item in items]
    except (KeyError, TypeError):
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if not na or not nb:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def rerank(con: sqlite3.Connection, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Reorder BM25 candidates by semantic similarity.

    Returns None when the embedding endpoint is unavailable, which leaves the
    caller with the untouched BM25 ordering. The endpoint is optional by
    design; the catalog must be fully usable with every model server down.
    """
    if not candidates:
        return None
    pool = candidates[:RERANK_CANDIDATES]
    texts = [query]
    for c in pool:
        texts.append(c["chunks"][0]["snippet"] if c["chunks"] else c["skill"])
    vecs = _embed(texts)
    if vecs is None or len(vecs) < 2:
        return None
    q = vecs[0]
    scored = []
    for c, v in zip(pool, vecs[1:]):
        c = dict(c)
        c["semantic"] = round(_cosine(q, v), 4)
        scored.append(c)
    # Blend: lexical score keeps primacy, semantic only reorders near-ties.
    max_lex = max((c["score"] for c in scored), default=1.0) or 1.0
    for c in scored:
        c["score"] = round(c["score"] / max_lex * 0.7 + c["semantic"] * 0.3, 4)
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored + candidates[RERANK_CANDIDATES:]


def embedding_available() -> bool:
    """Cheap liveness probe for the optional re-ranker."""
    try:
        req = urllib.request.Request(f"{EMBEDDING_URL.rstrip('/')}/../../health")
    except Exception:
        return False
    # The embeddings endpoint has no guaranteed /health, so probe with a
    # minimal embed call instead of guessing at a health path.
    return _embed(["ping"]) is not None


# --------------------------------------------------------------------------
# public entry point
# --------------------------------------------------------------------------

def search(
    con: sqlite3.Connection,
    query: str,
    limit: int = DEFAULT_LIMIT,
    *,
    rerank_enabled: bool = True,
    explain: bool = False,
) -> dict[str, Any]:
    """Search the catalog. Returns a dict with results and retrieval metadata."""
    tokens = tokenize(query)
    if not tokens:
        return {
            "query": query,
            "tier": "bm25",
            "results": [],
            "tokens": [],
            "note": "Query contained only stopwords; nothing to search for.",
        }

    rows = _bm25_leg(con, tokens, CANDIDATE_POOL)
    df, idf = _term_stats(con, tokens)
    token_hits = _token_hits(con, tokens)
    results = _aggregate(rows, token_hits, idf)

    tier = "bm25"
    if rerank_enabled and results:
        reordered = rerank(con, query, results)
        if reordered is not None:
            results = reordered
            tier = "bm25+rerank"

    results = results[:limit]

    if explain:
        for r in results:
            r["term_idf"] = {t: round(idf[t], 3) for t in r.get("matched_terms", []) if t in idf}

    return {
        "query": query,
        "tier": tier,
        "tokens": tokens,
        "candidate_chunks": len(rows),
        "results": results,
    }
