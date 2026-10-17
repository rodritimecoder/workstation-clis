#!/usr/bin/env python3
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from orchestra_conductor import OrchestraConductor


class TestGlitchOrchestra(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="test_orchestra_")
        self.conductor = OrchestraConductor(Path(self.td))

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_01_session_lifecycle(self):
        s = self.conductor.register_child_session("subagent_01", "Refactor models", "tty_01")
        self.assertEqual(s["status"], "running")

        st1 = self.conductor.status()
        self.assertEqual(st1["active_count"], 1)

        c = self.conductor.mark_session_complete("subagent_01", "Models refactored cleanly")
        self.assertEqual(c["status"], "completed")

        st2 = self.conductor.status()
        self.assertEqual(st2["active_count"], 0)
        self.assertEqual(st2["completed_count"], 1)
        print("  ✓ session lifecycle · verified")

    def test_02_completion_alert(self):
        res = self.conductor.trigger_completion_alert("Run complete")
        self.assertEqual(res["alert_message"], "Run complete")
        self.assertTrue(res["bell_emitted"])
        print("  ✓ completion alert · verified")


if __name__ == "__main__":
    print("\n🧪 Running Glitch Orchestra Test Suite:")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGlitchOrchestra)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
