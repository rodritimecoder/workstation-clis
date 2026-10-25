#!/usr/bin/env python3
"""The Go agent's local guards, which must hold without a network call."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import go_agent  # noqa: E402


class TestGoAgent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "notes.md").write_text("hello\n", encoding="utf-8")
        (self.root / "sub").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_read_stays_inside_the_checkout(self):
        result, _ = go_agent.dispatch("read_file", {"path": "../../etc/passwd"}, self.root)
        self.assertIn("refused", result)
        print("  ✓ read_file refuses a path outside the checkout")

    def test_02_write_stays_inside_the_checkout(self):
        result, _ = go_agent.dispatch("write_file", {"path": "../escape.txt", "content": "x"}, self.root)
        self.assertIn("refused", result)
        self.assertFalse((self.root.parent / "escape.txt").exists())
        print("  ✓ write_file refuses a path outside the checkout")

    def test_03_reading_and_writing_a_real_file(self):
        text, _ = go_agent.dispatch("read_file", {"path": "notes.md"}, self.root)
        self.assertEqual(text, "hello\n")
        written, _ = go_agent.dispatch("write_file", {"path": "sub/new.txt", "content": "ok"}, self.root)
        self.assertIn("wrote", written)
        self.assertEqual((self.root / "sub" / "new.txt").read_text(), "ok")
        print("  ✓ read and write work inside the checkout")

    def test_04_bash_refuses_git_push(self):
        result, _ = go_agent.dispatch("run_bash", {"command": "git push origin main"}, self.root)
        self.assertIn("refused", result)
        print("  ✓ run_bash refuses git push")

    def test_05_bash_runs_a_harmless_command(self):
        result, _ = go_agent.dispatch("run_bash", {"command": "echo guarded"}, self.root)
        self.assertIn("guarded", result)
        print("  ✓ run_bash runs a harmless command")

    def test_06_finish_signals_the_loop_to_stop(self):
        summary, done = go_agent.dispatch("finish", {"summary": "nothing to do"}, self.root)
        self.assertTrue(done)
        self.assertEqual(summary, "nothing to do")
        print("  ✓ finish returns the summary and stops the loop")

    def test_07_an_anthropic_shape_model_is_refused_before_the_call(self):
        import subprocess
        res = subprocess.run(
            [sys.executable, str(Path(go_agent.__file__)), "--task", "x", "--model", "claude-haiku-5-5"],
            capture_output=True,
            text=True,
            env={"OPENCODE_GO_TOKEN": "x", "PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("anthropic", res.stderr)
        self.assertIn("deepseek", res.stderr)
        print("  ✓ a model on another protocol is refused with an alternative")

    def test_08_an_unknown_tool_is_reported_not_crashed(self):
        result, done = go_agent.dispatch("rm_everything", {}, self.root)
        self.assertIn("unknown tool", result)
        self.assertFalse(done)
        print("  ✓ an unknown tool is a message, not an exception")


if __name__ == "__main__":
    unittest.main(verbosity=2)
