---
name: semantic-cache
description: >
  Sub-10ms repeat query bypass and verified response cache for RAG and agent systems (Glitch Cat Club / Kem Glitch;
  Reel DdbQeb5t2u0). Intercepts recurring queries via dense vector cosine similarity before invoking heavy RAG pipelines
  or frontier LLMs, delivering instant answers at $0 token cost for 40-70% of inbound queries.
metadata:
  creator: kem_glitch
  source_reel:
    id: DdbQeb5t2u0
    url: https://www.instagram.com/reel/DdbQeb5t2u0/
    vault_note: kem_glitch/2026-10-17_building_a_semantic_cache/notes.md
---

# Semantic Cache (`semantic-cache`)

A zero-token sub-10ms query bypass layer derived from **Kem Glitch (Glitch Cat Club)**'s architecture in Reel [`DdbQeb5t2u0`](https://www.instagram.com/reel/DdbQeb5t2u0/).

---

## 🏛️ Why Semantic Caching Matters

In production agent and RAG workflows, **40% to 70% of inbound user queries are semantic variations of recurring questions**. 
- Traditional RAG slurps documents, parses vectors, and calls an LLM every turn (3–10s, $$$).
- A **Semantic Cache** intercepts questions via vector cosine similarity and returns the verified ground-truth answer in **<10ms at $0 cost**.

---

## 🛠️ CLI Quickstart

```bash
CACHE="python3 /run/media/rodri/AI/skills/semantic-cache/semantic_cache.py"

# 1. Store a verified answer
$CACHE store "How do I configure git worktrees for parallel agents?" \
             "Run 'git worktree add <path> -b <branch>' and pre-claim file lines."

# 2. Query with paraphrase (Sub-10ms bypass)
$CACHE query "How to set up git worktrees for parallel subagents?"
# Output:
# ⚡ [CACHE HIT] Similarity: 89.2% (Hits: 1)
# Matched: "How do I configure git worktrees for parallel agents?"
# Answer: Run 'git worktree add <path> -b <branch>' and pre-claim file lines.

# 3. Check cache hit metrics
$CACHE stats
```
