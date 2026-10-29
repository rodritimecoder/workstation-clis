"""Tests for the plan executor: generated bindings and `omnicli exec`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog import bindings, builder  # noqa: E402

OMNICLI = str(ROOT / "omnicli.py")


class TestBindings(unittest.TestCase):
    def test_generated_module_exposes_the_plan_api(self):
        con = builder.connect()
        source = bindings.module_source(con)
        for symbol in ("def search(", "def describe(", "def invoke(", "def output(", "TOOL_IDS"):
            self.assertIn(symbol, source)

    def test_write_emits_an_importable_module(self):
        con = builder.connect()
        with tempfile.TemporaryDirectory() as tmp:
            out = bindings.write(con, Path(tmp))
            module = out / "omnicli_tools.py"
            self.assertTrue(module.is_file())
            spec = __import__("importlib.util", fromlist=["spec"]).spec_from_file_location(
                "omnicli_tools_probe", module)
            loaded = __import__("importlib.util", fromlist=["module_from_spec"]).module_from_spec(spec)
            spec.loader.exec_module(loaded)
            self.assertGreater(len(loaded.TOOL_IDS), 0)


class TestExec(unittest.TestCase):
    def _exec(self, plan: Path, *extra: str) -> dict:
        proc = subprocess.run(
            [sys.executable, OMNICLI, "exec", str(plan), "--json", *extra],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_one_plan_runs_several_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.py"
            plan.write_text(
                "from omnicli_tools import search\n"
                "print(','.join(r['skill'] for r in search('audio transcription', limit=2)))\n",
                encoding="utf-8",
            )
            report = self._exec(plan)
            self.assertTrue(report["sandboxed"])
            self.assertEqual(report["tool_calls"], 1)
            self.assertIn("audiocpp", report["stdout"])

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap not installed")
    def test_sandbox_blocks_writes_outside_the_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "probe.py"
            plan.write_text(
                "import os\n"
                "outside = '/home/omnicli-sandbox-probe.txt'\n"
                "try:\n"
                "    open(outside, 'w').write('x')\n"
                "    print('wrote')\n"
                "except OSError:\n"
                "    print('blocked')\n",
                encoding="utf-8",
            )
            report = self._exec(plan)
            self.assertEqual(report["stdout"].strip(), "blocked")
            self.assertFalse(os.path.exists("/home/omnicli-sandbox-probe.txt"))


class TestContractIsolation(unittest.TestCase):
    def test_help_probe_cannot_write_into_the_caller_directory(self):
        from catalog import registry

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "noisy.py"
            script.write_text(
                "import pathlib, sys\n"
                "if '--help' in sys.argv:\n"
                "    pathlib.Path(sys.argv[1]).mkdir(exist_ok=True)\n"
                "print('usage: noisy [-h]')\n",
                encoding="utf-8",
            )
            registry.extract_contract(script)
            self.assertFalse((Path(tmp) / "--help").exists())


if __name__ == "__main__":
    unittest.main()
