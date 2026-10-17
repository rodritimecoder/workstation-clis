#!/usr/bin/env python3
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from cache_engine import SemanticCache, cosine_similarity


class TestSemanticCache(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="test_cache_")
        self.db_path = Path(self.td) / "cache.db"
        self.cache = SemanticCache(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_01_cache_hit_identical(self):
        q = "How do I configure git worktrees for parallel agents?"
        ans = "Use 'git worktree add <path> -b <branch>' and pre-claim file lines."
        self.cache.set(q, ans)

        res = self.cache.get(q, threshold=0.90)
        self.assertTrue(res["hit"])
        self.assertEqual(res["answer"], ans)
        self.assertGreaterEqual(res["similarity"], 0.95)
        print("  ✓ identical hit · verified")

    def test_02_cache_hit_paraphrase(self):
        q1 = "How do I configure git worktrees for parallel agents?"
        ans = "Use 'git worktree add <path> -b <branch>' and pre-claim file lines."
        self.cache.set(q1, ans)

        q2 = "How to configure git worktrees for parallel subagents?"
        res = self.cache.get(q2, threshold=0.75)
        self.assertTrue(res["hit"])
        self.assertEqual(res["answer"], ans)
        print("  ✓ paraphrase hit · verified")

    def test_03_cache_miss_unrelated(self):
        q1 = "How do I configure git worktrees for parallel agents?"
        ans = "Use 'git worktree add <path> -b <branch>' and pre-claim file lines."
        self.cache.set(q1, ans)

        q2 = "What is the capital city of Australia?"
        res = self.cache.get(q2, threshold=0.75)
        self.assertFalse(res["hit"])
        print("  ✓ unrelated miss · verified")

    def test_04_stats_and_purge(self):
        self.cache.set("q1", "a1")
        self.cache.set("q2", "a2")
        self.cache.get("q1")
        st = self.cache.stats()
        self.assertEqual(st["total_entries"], 2)
        self.assertEqual(st["total_cache_hits"], 1)

        purged = self.cache.purge()
        self.assertEqual(purged, 2)
        st2 = self.cache.stats()
        self.assertEqual(st2["total_entries"], 0)
        print("  ✓ stats and purge · verified")


if __name__ == "__main__":
    print("\n🧪 Running Semantic Cache Test Suite:")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSemanticCache)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
