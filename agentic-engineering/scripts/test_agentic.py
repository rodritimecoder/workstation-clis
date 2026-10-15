#!/usr/bin/env python3
"""
test_agentic.py — Grounded Verification Test Suite for agentic-engineering
Tests Kem's full 7-step loop end-to-end in isolated temporary directories.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
AGENTIC_PY = SKILL_DIR / "agentic.py"


def test_agentic_pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "my_project"
        target.mkdir()

        # Step 1: Initialize Kanban Board
        res_init = subprocess.run([sys.executable, str(AGENTIC_PY), "init", str(target)], capture_output=True, text=True)
        assert res_init.returncode == 0, f"Init failed: {res_init.stderr}"
        assert (target / ".kanban" / "01_new" / "CARD-001_example.md").is_file(), "CARD-001_example.md missing"

        # Step 2: Render Board
        res_list = subprocess.run([sys.executable, str(AGENTIC_PY), "kanban", "list", str(target)], capture_output=True, text=True)
        assert res_list.returncode == 0, f"List failed: {res_list.stderr}"
        assert "CARD-001" in res_list.stdout

        # Step 3: Add Card 2
        res_add = subprocess.run([sys.executable, str(AGENTIC_PY), "kanban", "add", "Build Navigation Bar", "--target", str(target)], capture_output=True, text=True)
        assert res_add.returncode == 0, f"Add failed: {res_add.stderr}"
        assert list((target / ".kanban" / "01_new").glob("CARD-002*.md")), "CARD-002 was not created"

        # Step 4: The Listener
        res_listen = subprocess.run([sys.executable, str(AGENTIC_PY), "listen", str(target), "--once"], capture_output=True, text=True)
        assert res_listen.returncode == 0, f"Listen failed: {res_listen.stderr}"
        assert (target / ".kanban" / "02_picked_up" / "CARD-001_example.md").is_file(), "CARD-001 not picked up by Listener"

        # Step 5: The Splitter
        res_split = subprocess.run([sys.executable, str(AGENTIC_PY), "split", "Billing Dashboard", "--json"], capture_output=True, text=True)
        assert res_split.returncode == 0, f"Split failed: {res_split.stderr}"
        plan = json.loads(res_split.stdout)
        assert plan["total_lanes"] == 3
        assert plan["lanes"][0]["sandbox"] == "sandbox-1"

        # Step 6: Full 7-Step Pipeline Run with Judge Approval
        res_run = subprocess.run([sys.executable, str(AGENTIC_PY), "run", "CARD-001", str(target), "--mock-judge", "PASS"], capture_output=True, text=True)
        assert res_run.returncode == 0, f"Run pipeline failed: {res_run.stderr}"
        assert "Kem's 7-Step Loop" in res_run.stdout
        assert "All 3 parallel sandboxes completed & verified" in res_run.stdout
        assert (target / ".kanban" / "04_done" / "CARD-001_example.md").is_file(), "CARD-001 not in done/"

        # Step 7: Kem's Pink Arrow (Rejection Delta Test)
        res_reject = subprocess.run([sys.executable, str(AGENTIC_PY), "run", "CARD-002", str(target), "--mock-judge", "FAIL"], capture_output=True, text=True)
        assert res_reject.returncode == 1, "Expected rejection to halt with code 1"
        assert "Kem's Pink Arrow triggered" in res_reject.stdout

        print("\n🎉 All 7 steps of the Agentic Engineering loop verified and passed!")


if __name__ == "__main__":
    test_agentic_pipeline_end_to_end()
