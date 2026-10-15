#!/usr/bin/env python3
"""
graph_memory.py — Unified CLI for Local Graph Memory & RAG
"""

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
RAG_DIR = SKILL_DIR / "rag"

def main():
    parser = argparse.ArgumentParser(
        prog="graph-memory",
        description="Local hybrid graph-memory RAG and exact-quote distillation engine"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # 1. search
    p_search = sub.add_parser("search", help="Search the index via hybrid BM25 + vector reciprocal rank fusion")
    p_search.add_argument("query", help="Query string")

    # 2. index
    p_index = sub.add_parser("index", help="Rebuild the index over notes corpus")
    p_index.add_argument("--corpus", default="/run/media/rodri/AI/University/notes", help="Path to notes directory")

    # 3. distil
    p_distil = sub.add_parser("distil", help="Distil markdown notes into verified question-rule-quote triplets")
    p_distil.add_argument("corpus", nargs="?", default="/run/media/rodri/AI/University/notes", help="Path to notes directory")
    p_distil.add_argument("--limit", type=int, default=None, help="Limit number of notes to process")

    args = parser.parse_args()

    if args.action == "search":
        cmd = [sys.executable, str(RAG_DIR / "search.py"), args.query]
        sys.exit(subprocess.run(cmd).returncode)
    elif args.action == "index":
        cmd = [sys.executable, str(RAG_DIR / "build_index.py"), "--corpus", args.corpus]
        sys.exit(subprocess.run(cmd).returncode)
    elif args.action == "distil":
        cmd = [sys.executable, str(RAG_DIR / "distil.py"), args.corpus]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        sys.exit(subprocess.run(cmd).returncode)

if __name__ == "__main__":
    main()
