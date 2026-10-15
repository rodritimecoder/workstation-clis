#!/usr/bin/env python3
"""
test_factory.py — Grounded Verification Test Suite for uber-hub-factory
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FACTORY_PY = SKILL_DIR / "scripts" / "factory.py"


def test_factory_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        fake_skills_dir = tmp_path / "skills"
        fake_skills_dir.mkdir()

        # Create 2 mock skills
        s1 = fake_skills_dir / "mock-tool-a"
        s1.mkdir()
        (s1 / "scripts").mkdir()
        (s1 / "SKILL.md").write_text("---\nname: mock-tool-a\ndescription: Mock Tool A for test\n---\n# Mock A\n", encoding="utf-8")
        (s1 / "scripts" / "tool_a.py").write_text("#!/usr/bin/env python3\nprint('Hello from tool A')\n", encoding="utf-8")
        os.chmod(s1 / "scripts" / "tool_a.py", 0o755)

        s2 = fake_skills_dir / "mock-tool-b"
        s2.mkdir()
        (s2 / "scripts").mkdir()
        (s2 / "SKILL.md").write_text("---\nname: mock-tool-b\ndescription: Mock Tool B for test\n---\n# Mock B\n", encoding="utf-8")
        (s2 / "scripts" / "tool_b.py").write_text("#!/usr/bin/env python3\nprint('Hello from tool B')\n", encoding="utf-8")
        os.chmod(s2 / "scripts" / "tool_b.py", 0o755)

        # Import factory logic and test stage 1 + stage 2
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        import factory
        factory.CANONICAL_SKILLS_DIR = fake_skills_dir

        # Run Stage 1 (Inventory)
        manifest = factory.stage1_inventory(["mock-tool-a", "mock-tool-b"])
        assert "mock-tool-a" in manifest["skills"]
        assert "mock-tool-b" in manifest["skills"]
        assert manifest["skills"]["mock-tool-a"]["scripts"] == ["tool_a.py"]

        # Run Stage 2 (Scaffold Hub)
        hub_dir = factory.stage2_scaffold("test-hub", manifest, target_dir=fake_skills_dir / "test-hub")
        assert (hub_dir / "test-hub.py").is_file()
        assert (hub_dir / "SKILL.md").is_file()
        assert (hub_dir / "suites" / "mock-tool-a" / "rubric.md").is_file()

        # Crucial Invariant: ZERO nested SKILL.md files inside suites/
        nested_skills = list((hub_dir / "suites").rglob("SKILL.md"))
        assert len(nested_skills) == 0, f"Found nested SKILL.md files: {nested_skills}"

        # Test hub execution
        res_list = subprocess.run([sys.executable, str(hub_dir / "test-hub.py"), "list"], capture_output=True, text=True)
        assert res_list.returncode == 0
        assert "mock-tool-a" in res_list.stdout

        res_inspect = subprocess.run([sys.executable, str(hub_dir / "test-hub.py"), "inspect", "mock-tool-a"], capture_output=True, text=True)
        assert res_inspect.returncode == 0
        assert "Mock A" in res_inspect.stdout

        res_run = subprocess.run([sys.executable, str(hub_dir / "test-hub.py"), "run", "mock-tool-a"], capture_output=True, text=True)
        assert res_run.returncode == 0
        assert "Hello from tool A" in res_run.stdout

        print("✅ All factory unit & pipeline integration tests passed!")


if __name__ == "__main__":
    test_factory_end_to_end()
