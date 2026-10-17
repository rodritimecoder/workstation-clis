import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestICMArchitect(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_icm_"))
        self.cli = "/run/media/rodri/AI/skills/icm-architect/scripts/icm_architect.py"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_scaffold_and_validate(self):
        ws = self.tmp_dir / "my_pipeline"
        res = subprocess.run(
            ["python3", self.cli, "init", str(ws), "--name", "Test Pipeline", "--stages", "ingest,process,publish", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "scaffolded")
        self.assertEqual(len(data["stages"]), 3)

        self.assertTrue((ws / "AGENTS.md").is_file())
        self.assertTrue((ws / "CONTEXT.md").is_file())
        self.assertTrue((ws / "01_ingest" / "CONTEXT.md").is_file())
        self.assertTrue((ws / "02_process" / "CONTEXT.md").is_file())
        self.assertTrue((ws / "03_publish" / "CONTEXT.md").is_file())
        self.assertTrue((ws / "_shared" / "rules.md").is_file())

        val_res = subprocess.run(
            ["python3", self.cli, "validate", str(ws), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        val_data = json.loads(val_res.stdout)
        self.assertEqual(val_data["status"], "PASS")
        self.assertEqual(len(val_data["errors"]), 0)

    def test_broken_reference_detection(self):
        ws = self.tmp_dir / "broken_pipeline"
        subprocess.run(
            ["python3", self.cli, "init", str(ws), "--stages", "step1,step2"],
            capture_output=True,
            text=True,
            check=True,
        )

        broken_file = ws / "01_step1" / "broken.md"
        broken_file.write_text("[ghost link](non_existent_folder/missing.md)", encoding="utf-8")

        val_res = subprocess.run(
            ["python3", self.cli, "validate", str(ws), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(val_res.returncode, 1)
        val_data = json.loads(val_res.stdout)
        self.assertEqual(val_data["status"], "FAIL")
        self.assertTrue(any("non_existent_folder/missing.md" in err for err in val_data["errors"]))

    def test_map_mermaid(self):
        ws = self.tmp_dir / "map_pipeline"
        subprocess.run(
            ["python3", self.cli, "init", str(ws), "--stages", "stage_a,stage_b"],
            capture_output=True,
            text=True,
            check=True,
        )
        res = subprocess.run(
            ["python3", self.cli, "map", str(ws), "--mermaid"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("flowchart LR", res.stdout)
        self.assertIn("Stage A", res.stdout)


if __name__ == "__main__":
    unittest.main()
