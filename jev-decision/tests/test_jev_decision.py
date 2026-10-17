#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from jev_engine import JevEngine


class TestJevDecision(unittest.TestCase):
    def setUp(self):
        self.engine = JevEngine()

    def test_01_bool_primitive(self):
        # Superseded contradiction
        ctx = "Architecture note: Postgres 14 was deprecated and replaced with SQLite 3."
        q = "Does SQLite supersede Postgres?"
        res = self.engine.decide_bool(ctx, q)
        self.assertIn("decision", res)
        self.assertIn("confidence", res)
        self.assertTrue(res["decision"])
        print("  ✓ bool · verified")

    def test_02_choice_primitive(self):
        ctx = "The user specified that integration tests must run in parallel across CPU cores."
        q = "Which execution mode should be chosen?"
        options = ["sequential_lane", "parallel_worker_lane", "skip_tests"]
        res = self.engine.decide_choice(ctx, q, options)
        self.assertEqual(res["selection"], "parallel_worker_lane")
        self.assertGreater(res["confidence"], 0.3)
        print("  ✓ choice · verified")

    def test_03_score_primitive(self):
        ctx = "Complete unit test coverage for authentication module with 0 failing assertions."
        criteria = "unit test coverage and zero failure assertions"
        res = self.engine.decide_score(ctx, criteria)
        self.assertGreater(res["score"], 0.7)
        print("  ✓ score · verified")

    def test_04_context_cleaning_pairwise(self):
        claims = [
            {"timestamp": "2026-01-01", "text": "Deploy target is AWS ECS cluster."},
            {"timestamp": "2026-06-01", "text": "AWS ECS cluster is obsolete, migrated to local Podman."},
        ]
        res = self.engine.clean_context_claims(claims)
        self.assertEqual(res["total_input_claims"], 2)
        self.assertEqual(res["active_claims_retained"], 1)
        self.assertEqual(res["superseded_count"], 1)
        self.assertEqual(res["active"][0]["timestamp"], "2026-06-01")
        print("  ✓ context clean · verified")

    def test_05_uat_action_selection(self):
        dom = [
            {"id": "btn_cancel", "text": "Cancel and Return"},
            {"id": "btn_submit_order", "text": "Confirm & Place Order"},
            {"id": "nav_help", "text": "Help Center"},
        ]
        intent = "Submit the order now"
        res = self.engine.evaluate_uat_target(dom, intent)
        self.assertEqual(res["selected_id"], "btn_submit_order")
        print("  ✓ uat action · verified")


if __name__ == "__main__":
    print("\n🧪 Running JEV Decision Engine Test Suite:")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJevDecision)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
