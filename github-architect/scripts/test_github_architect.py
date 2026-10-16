import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules under test
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import github_architect
import git_sync


class TestGitHubArchitect(unittest.TestCase):
    def test_render_table(self):
        rows = [
            {"repository": "repo-a", "branch": "main", "worktree": "Clean", "remote_sync": "Up to date"},
            {"repository": "repo-b", "branch": "dev", "worktree": "2 dirty", "remote_sync": "Ahead (1)"},
        ]
        table = github_architect.render_table(rows, ["repository", "branch", "worktree"])
        self.assertIn("| Repository | Branch | Worktree |", table)
        self.assertIn("| repo-a     | main   | Clean    |", table)
        self.assertIn("| repo-b     | dev    | 2 dirty  |", table)

    def test_render_table_empty(self):
        table = github_architect.render_table([])
        self.assertEqual(table, "*(no records)*\n")

    def test_get_fleet_status_records(self):
        fleet = [
            {"name": "test-repo", "path": Path("/fake/path"), "description": "Fake repo"}
        ]

        def fake_run_cmd(cmd, cwd=None, check=True):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            mock = MagicMock()
            mock.returncode = 0
            if "rev-parse" in cmd_str:
                mock.stdout = "main\n"
            elif "status --porcelain" in cmd_str:
                mock.stdout = ""
            elif "rev-list" in cmd_str:
                mock.stdout = "0 0\n"
            elif "log -1" in cmd_str:
                mock.stdout = "abc1234 (1 day ago) - feat: test commit\n"
            else:
                mock.stdout = ""
            return mock

        with patch.object(github_architect, "run_cmd", side_effect=fake_run_cmd):
            records = github_architect.get_fleet_status_records(fleet)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["repository"], "test-repo")
            self.assertEqual(records[0]["branch"], "main")
            self.assertEqual(records[0]["worktree"], "Clean")
            self.assertEqual(records[0]["remote_sync"], "Up to date")
            self.assertIn("abc1234", records[0]["last_commit"])

    def test_cmd_status_all_json_and_projection(self):
        fleet = [
            {"name": "repo-1", "path": Path("/tmp/r1"), "description": "desc 1"},
            {"name": "repo-2", "path": Path("/tmp/r2"), "description": "desc 2"},
        ]
        records = [
            {"repository": "repo-1", "branch": "main", "worktree": "Clean", "remote_sync": "Up to date", "last_commit": "c1", "path": "/tmp/r1"},
            {"repository": "repo-2", "branch": "feat", "worktree": "1 dirty", "remote_sync": "Ahead (1)", "last_commit": "c2", "path": "/tmp/r2"},
        ]

        with patch.object(github_architect, "discover_fleet_repos", return_value=fleet), \
             patch.object(github_architect, "get_fleet_status_records", return_value=records):
            
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                github_architect.cmd_status_all(as_json=True, project_keys=["repository", "branch"], limit=1)
            
            output = buf.getvalue().strip()
            data = json.loads(output)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0], {"repository": "repo-1", "branch": "main"})

    def test_cmd_status_all_table(self):
        fleet = [{"name": "repo-1", "path": Path("/tmp/r1"), "description": "desc 1"}]
        records = [{"repository": "repo-1", "branch": "main", "worktree": "Clean", "remote_sync": "Up to date", "last_commit": "c1", "path": "/tmp/r1"}]

        with patch.object(github_architect, "discover_fleet_repos", return_value=fleet), \
             patch.object(github_architect, "get_fleet_status_records", return_value=records):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                github_architect.cmd_status_all(as_table=True)
            output = buf.getvalue()
            self.assertIn("### Workstation Fleet Status", output)
            self.assertIn("| Repository | Branch | Worktree |", output)
            self.assertIn("| repo-1     | main   | Clean    |", output)

    def test_cmd_audit_table_and_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "README.md").write_text("# Test\n", encoding="utf-8")

            # Test JSON mode
            buf = io.StringIO()
            with patch("sys.stdout", buf), \
                 patch.object(github_architect, "check_gh_status", return_value=(True, "testuser")), \
                 patch.object(github_architect, "run_cmd", return_value=MagicMock(stdout="", returncode=0)):
                github_architect.cmd_audit(tmppath, as_json=True)
            output = buf.getvalue().strip()
            data = json.loads(output)
            self.assertIn("checks", data)
            items = {c["item"]: c["status"] for c in data["checks"]}
            self.assertEqual(items.get("README.md"), "Yes")
            self.assertEqual(items.get(".gitignore"), "Missing")

            # Test Table mode
            buf = io.StringIO()
            with patch("sys.stdout", buf), \
                 patch.object(github_architect, "check_gh_status", return_value=(True, "testuser")), \
                 patch.object(github_architect, "run_cmd", return_value=MagicMock(stdout="", returncode=0)):
                github_architect.cmd_audit(tmppath, as_table=True)
            table_out = buf.getvalue()
            self.assertIn("### Repository Audit:", table_out)
            self.assertIn("| Audit Check", table_out)
            self.assertIn("| README.md", table_out)


class TestGitSync(unittest.TestCase):
    def test_git_sync_render_table(self):
        rows = [
            {"step": "Branch", "status": "main", "details": "origin/main"},
            {"step": "Push", "status": "Success", "details": "Pushed upstream"},
        ]
        table = git_sync.render_table(rows, ["step", "status", "details"])
        self.assertIn("| Step   | Status  | Details         |", table)
        self.assertIn("| Branch | main    | origin/main     |", table)


if __name__ == "__main__":
    unittest.main()
