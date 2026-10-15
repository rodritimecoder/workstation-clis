#!/usr/bin/env python3
"""
test_factory.py — Grounded Verification Test Suite for Non-Destructive uber-hub-factory
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import factory


def test_factory_bridge_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        fake_skills_dir = tmp_path / "skills"
        fake_skills_dir.mkdir()

        # Create 2 mock standalone skills
        s1 = fake_skills_dir / "mock-tool-a"
        s1.mkdir()
        (s1 / "scripts").mkdir()
        s1_skill_md = "---\nname: mock-tool-a\ndescription: Mock Tool A for test\n---\n# Mock Tool A\nStandalone documentation.\n"
        (s1 / "SKILL.md").write_text(s1_skill_md, encoding="utf-8")
        s1_script = s1 / "scripts" / "tool_a.py"
        s1_script.write_text("#!/usr/bin/env python3\nimport sys\nprint('Hello from tool A', sys.argv[1:])\n", encoding="utf-8")
        s1_script.chmod(0o755)

        s2 = fake_skills_dir / "mock-tool-b"
        s2.mkdir()
        (s2 / "scripts").mkdir()
        s2_skill_md = "---\nname: mock-tool-b\ndescription: Mock Tool B for test\n---\n# Mock Tool B\nStandalone documentation.\n"
        (s2 / "SKILL.md").write_text(s2_skill_md, encoding="utf-8")
        s2_script = s2 / "scripts" / "tool_b.py"
        s2_script.write_text("#!/usr/bin/env python3\nimport sys\nprint('Hello from tool B', sys.argv[1:])\n", encoding="utf-8")
        s2_script.chmod(0o755)

        # Override canonical directory in factory module
        factory.CANONICAL_SKILLS_DIR = fake_skills_dir

        # 1. Test Stage 1: Discover
        m_file = tmp_path / "manifest.json"
        manifest = factory.stage1_discover(["mock-tool-a", "mock-tool-b"], output_file=m_file)
        assert "mock-tool-a" in manifest["skills"], "mock-tool-a not discovered"
        assert "mock-tool-b" in manifest["skills"], "mock-tool-b not discovered"
        assert manifest["skills"]["mock-tool-a"]["scripts"] == ["tool_a.py"]
        assert m_file.is_file(), "Manifest file not created"

        # 2. Test Stage 2: Bridge & Scaffold
        hub_dir = fake_skills_dir / "test-hub"
        factory.stage2_bridge("test-hub", manifest, target_dir=hub_dir, link_bin=False)

        assert (hub_dir / "test-hub.py").is_file(), "Hub router test-hub.py missing"
        assert (hub_dir / "SKILL.md").is_file(), "Hub SKILL.md missing"
        assert (hub_dir / "README.md").is_file(), "Hub README.md missing"

        # NON-DESTRUCTIVE INVARIANTS:
        # A) Standalone skills still exist in original location
        assert (s1 / "SKILL.md").is_file(), "Original s1 SKILL.md was modified or deleted!"
        assert (s1 / "SKILL.md").read_text(encoding="utf-8") == s1_skill_md, "Original s1 SKILL.md content changed!"
        assert (s2 / "SKILL.md").is_file(), "Original s2 SKILL.md was modified or deleted!"
        assert (s2 / "SKILL.md").read_text(encoding="utf-8") == s2_skill_md, "Original s2 SKILL.md content changed!"
        # B) Hub does NOT copy into suites/ or delete source skills
        assert not (hub_dir / "suites").exists(), "Hub should not create duplicate suites/ directory!"

        # 3. Test Hub CLI Commands
        hub_bin = hub_dir / "test-hub.py"

        # A: list
        res_list = subprocess.run([sys.executable, str(hub_bin), "list"], capture_output=True, text=True)
        assert res_list.returncode == 0, f"list failed: {res_list.stderr}"
        assert "mock-tool-a" in res_list.stdout
        assert "mock-tool-b" in res_list.stdout

        # B: search
        res_search = subprocess.run([sys.executable, str(hub_bin), "search", "tool"], capture_output=True, text=True)
        assert res_search.returncode == 0, f"search failed: {res_search.stderr}"
        assert "mock-tool-a" in res_search.stdout

        # C: inspect (reads native SKILL.md dynamically!)
        res_inspect = subprocess.run([sys.executable, str(hub_bin), "inspect", "mock-tool-a"], capture_output=True, text=True)
        assert res_inspect.returncode == 0, f"inspect failed: {res_inspect.stderr}"
        assert "Mock Tool A" in res_inspect.stdout
        assert "Standalone documentation." in res_inspect.stdout

        # D: run (delegates to sibling script)
        res_run = subprocess.run([sys.executable, str(hub_bin), "run", "mock-tool-a", "arg1", "arg2"], capture_output=True, text=True)
        assert res_run.returncode == 0, f"run failed: {res_run.stderr}"
        assert "Hello from tool A ['arg1', 'arg2']" in res_run.stdout

        # E: direct suite shortcut ({hub} {suite} [args])
        res_direct = subprocess.run([sys.executable, str(hub_bin), "mock-tool-b", "foo"], capture_output=True, text=True)
        assert res_direct.returncode == 0, f"direct shortcut failed: {res_direct.stderr}"
        assert "Hello from tool B ['foo']" in res_direct.stdout

        # 4. Test Stage 3: Verify
        report_file = tmp_path / "verification_report.json"
        report = factory.stage3_verify("test-hub", manifest, target_dir=hub_dir, output_file=report_file)
        assert report["all_passed"] is True, f"Stage 3 verification failed: {report}"
        assert report_file.is_file(), "Verification report file missing"

        print("\n🎉 All non-destructive ICM Bridge pipeline tests passed successfully!")


if __name__ == "__main__":
    test_factory_bridge_end_to_end()
