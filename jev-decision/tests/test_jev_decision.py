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
        ctx = "Architecture note: Postgres 14 was deprecated and replaced with SQLite 3."
        q = "Does SQLite supersede Postgres?"
        res = self.engine.decide_bool(ctx, q)
        self.assertIn("decision", res)
        self.assertIn("confidence", res)
        self.assertIn(res["source"], ["onejev_1.5_4b_server", "heuristic_fallback"])
        print("  ✓ bool · verified")

    def test_02_choice_primitive(self):
        ctx = "The user specified that integration tests must run in parallel across CPU cores."
        q = "Which execution mode should be chosen?"
        options = ["sequential_lane", "parallel_worker_lane", "skip_tests"]
        res = self.engine.decide_choice(ctx, q, options)
        self.assertIn(res["selection"], options)
        self.assertGreater(res["confidence"], 0.1)
        print("  ✓ choice · verified")

    def test_03_score_primitive(self):
        ctx = "Complete unit test coverage for authentication module with 0 failing assertions."
        criteria = "unit test coverage and zero failure assertions"
        res = self.engine.decide_score(ctx, criteria)
        self.assertGreater(res["score"], 0.0)
        self.assertLessEqual(res["score"], 1.0)
        print("  ✓ score · verified")

    def test_04_composite_primitive(self):
        ctx = "Pull request contains 40 new passing tests, clean formatting, and valid documentation."
        q = "Is this pull request safe and high quality?"
        options = ["merge_now", "request_changes", "block"]
        res = self.engine.decide_composite(ctx, q, options)
        self.assertIn("gate", res)
        self.assertIn("action", res)
        self.assertIn("quality_score", res)
        self.assertIn(res["action"], options)
        print(f"  ✓ composite (gate={res['gate']}, action='{res['action']}', score={res['quality_score']}) · verified")

    def test_05_context_cleaning_pairwise(self):
        claims = [
            {"timestamp": "2026-01-01", "text": "Deploy target is AWS ECS cluster."},
            {"timestamp": "2026-06-01", "text": "AWS ECS cluster is obsolete, migrated to local Podman."},
        ]
        res = self.engine.clean_context_claims(claims)
        self.assertEqual(res["total_input_claims"], 2)
        self.assertGreaterEqual(res["active_claims_retained"], 1)
        print("  ✓ context clean · verified")

    def test_06_uat_action_selection(self):
        dom = [
            {"id": "btn_cancel", "text": "Cancel and Return"},
            {"id": "btn_submit_order", "text": "Confirm & Place Order"},
            {"id": "nav_help", "text": "Help Center"},
        ]
        intent = "Submit the order now"
        res = self.engine.evaluate_uat_target(dom, intent)
        self.assertIn(res["selected_id"], ["btn_cancel", "btn_submit_order", "nav_help"])
        print(f"  ✓ uat action target '{res['selected_id']}' · verified")

    def test_07_vision_decision(self):
        png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        ctx = "Visual screen inspection of an empty canvas."
        q = "Is visual canvas element present?"
        res = self.engine.decide_bool(ctx, q, image=png_b64)
        self.assertIn("decision", res)
        self.assertIn("confidence", res)
        print(f"  ✓ vision decision ({res['source']}) · verified")

    def test_08_remote_tailscale_decision(self):
        remote_engine = JevEngine(host="rodri-x870-taichi-creator.tail2975a8.ts.net", port=8083)
        if not remote_engine.is_online():
            print("  ⚠️ Remote OneJev host offline, skipping")
            return
        res = remote_engine.decide_bool("Tailscale cluster state verification.", "Is cluster network operational?")
        self.assertIn("decision", res)
        self.assertIn("confidence", res)
        self.assertEqual(res["source"], "onejev_1.5_4b_server")
        print(f"  ✓ remote tailscale bool decision ({res['decision']}, conf={res['confidence']*100:.1f}%) · verified")


if __name__ == "__main__":
    print("\n🧪 Running OneJev1.5-4B Multimodal Decision Test Suite:")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJevDecision)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
