import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules under test
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import github_architect
import git_sync
import publication_guard


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


class TestPublicationGuard(unittest.TestCase):
    # Built at runtime, never written as a literal: a PAT-shaped string in
    # this file would be published to the public spokes and the gate would
    # (correctly) block the bundle.
    FAKE_PAT = "ghp_" + "A" * 36

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _skill(self, name="skill", frontmatter="---\nname: s\ndescription: d\n---\n\nbody\n"):
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(frontmatter, encoding="utf-8")
        return d

    def test_clean_skill_passes(self):
        d = self._skill()
        findings = publication_guard.scan_source(d, "t")
        self.assertEqual([f for f in findings if f["severity"] == "block"], [])

    def test_archived_without_status_marker_is_blocked(self):
        d = self._skill()
        findings = publication_guard.scan_status_marker(d, "archived/s", "t")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "missing-status-marker")

    def test_archived_with_status_marker_passes(self):
        d = self._skill(frontmatter="---\nname: s\nstatus: archived\n---\n\nbody\n")
        findings = publication_guard.scan_status_marker(d, "archived/s", "t")
        self.assertEqual(findings, [])

    def test_non_archived_path_needs_no_marker(self):
        d = self._skill()
        self.assertEqual(publication_guard.scan_status_marker(d, "skill", "t"), [])

    def test_secret_filename_is_blocked(self):
        d = self._skill()
        (d / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        findings = publication_guard.scan_source(d, "t")
        self.assertEqual([f["kind"] for f in findings], ["secret-filename"])

    def test_env_example_is_allowed(self):
        d = self._skill()
        (d / ".env.example").write_text("TOKEN=x\n", encoding="utf-8")
        findings = publication_guard.scan_source(d, "t")
        self.assertEqual([f for f in findings if f["severity"] == "block"], [])

    def test_secret_content_is_blocked_and_masked(self):
        d = self._skill()
        (d / "leak.txt").write_text(self.FAKE_PAT + "\n", encoding="utf-8")
        findings = publication_guard.scan_source(d, "t")
        self.assertEqual(len(findings), 1)
        self.assertNotIn(self.FAKE_PAT, findings[0]["detail"])

    def test_placeholder_credential_is_allowed(self):
        d = self._skill()
        (d / "doc.md").write_text('api_key = "YOUR_API_KEY_HERE"\n', encoding="utf-8")
        findings = publication_guard.scan_source(d, "t")
        self.assertEqual([f for f in findings if f["severity"] == "block"], [])

    def test_excluded_paths_are_not_scanned(self):
        d = self._skill()
        (d / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        findings = publication_guard.scan_source(d, "t", excludes=[".env"])
        self.assertEqual([f for f in findings if f["severity"] == "block"], [])

    def test_reap_removes_only_stale_managed_dirs(self):
        (self.tmp / "old").mkdir()
        (self.tmp / "old" / "f.txt").write_text("x", encoding="utf-8")
        (self.tmp / "keep").mkdir()
        (self.tmp / "keep" / "f.txt").write_text("x", encoding="utf-8")
        managed = self.tmp / ".bundle-managed.json"
        managed.write_text(json.dumps({"managed": ["old", "keep"]}), encoding="utf-8")
        result = publication_guard.reap(self.tmp, managed, ["keep"])
        self.assertEqual(result["removed"], ["old"])
        self.assertFalse((self.tmp / "old").exists())
        self.assertTrue((self.tmp / "keep").exists())

    def test_reap_is_idempotent(self):
        managed = self.tmp / ".bundle-managed.json"
        managed.write_text(json.dumps({"managed": ["gone"]}), encoding="utf-8")
        first = publication_guard.reap(self.tmp, managed, [])
        second = publication_guard.reap(self.tmp, managed, [])
        self.assertEqual(first["removed"], ["gone"])
        self.assertEqual(second["removed"], [])


class TestGuardedCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        run = lambda *a: subprocess.run(["git", "-C", str(self.repo)] + list(a),
                                        capture_output=True, text=True, check=True)
        run("init", "-b", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        (self.repo / "keep.txt").write_text("fine\n", encoding="utf-8")
        run("add", "keep.txt")
        run("commit", "-m", "init")

    def test_clean_change_commits(self):
        (self.repo / "new.txt").write_text("hello\n", encoding="utf-8")
        result = git_sync.guarded_commit(str(self.repo), "sync: test")
        self.assertEqual(result["blocked"], [])
        self.assertEqual(len(result["committed"]), 1)
        self.assertIn("new.txt", subprocess.run(
            ["git", "-C", str(self.repo), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True, text=True).stdout)

    def test_untracked_file_with_secret_is_blocked(self):
        (self.repo / "leak.txt").write_text(TestPublicationGuard.FAKE_PAT + "\n", encoding="utf-8")
        result = git_sync.guarded_commit(str(self.repo), "sync: test")
        self.assertEqual(len(result["blocked"]), 1)
        self.assertEqual(result["committed"], [])
        # Nothing may reach the index.
        staged = subprocess.run(["git", "-C", str(self.repo), "diff", "--cached", "--name-only"],
                                capture_output=True, text=True).stdout
        self.assertEqual(staged.strip(), "")

    def test_modified_file_with_secret_is_blocked(self):
        (self.repo / "keep.txt").write_text(TestPublicationGuard.FAKE_PAT + "\n", encoding="utf-8")
        result = git_sync.guarded_commit(str(self.repo), "sync: test")
        self.assertEqual(len(result["blocked"]), 1)
        self.assertEqual(result["committed"], [])

    def test_deletion_is_allowed(self):
        (self.repo / "keep.txt").unlink()
        result = git_sync.guarded_commit(str(self.repo), "sync: test")
        self.assertEqual(result["blocked"], [])
        self.assertEqual(len(result["committed"]), 1)

    def test_exclude_keeps_a_path_out_of_the_commit(self):
        (self.repo / "new.txt").write_text("hello\n", encoding="utf-8")
        (self.repo / "draft.md").write_text("wip\n", encoding="utf-8")
        result = git_sync.guarded_commit(str(self.repo), "sync: test", excludes=["*.md"])
        self.assertEqual(result["blocked"], [])
        committed = subprocess.run(
            ["git", "-C", str(self.repo), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True, text=True).stdout
        self.assertIn("new.txt", committed)
        self.assertNotIn("draft.md", committed)

    def test_changed_files_includes_untracked(self):
        (self.repo / "brand_new.txt").write_text("x\n", encoding="utf-8")
        files = git_sync.changed_files_in(str(self.repo))
        self.assertIn("brand_new.txt", files)


class TestCommitMessage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.run = lambda *a: subprocess.run(["git", "-C", str(self.repo)] + list(a),
                                             capture_output=True, text=True, check=True)
        self.run("init", "-b", "main")
        self.run("config", "user.email", "t@t")
        self.run("config", "user.name", "t")

    def write(self, rel, text="x\n"):
        target = self.repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def test_subject_names_scope_and_file(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        self.run("add", "-A")
        subject = git_sync.describe_staged_changes(str(self.repo)).splitlines()[0]
        self.assertEqual(subject, "chore(kem-thought): SKILL.md (+1/-0)")

    def test_multiple_scopes_appear_in_subject(self):
        self.write("academic/academic-pipeline-v2/SKILL.md")
        self.write("academic/canvas-cli/scripts/gates.py")
        self.write("github-architect/scripts/git_sync.py")
        self.run("add", "-A")
        subject = git_sync.describe_staged_changes(str(self.repo)).splitlines()[0]
        self.assertIn("(academic-pipeline-v2, canvas-cli +1)", subject)
        self.assertIn("3 files", subject)

    def test_body_lists_every_path(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        self.write("glitch-cat/kem-thought/principles/code-decides.md")
        self.run("add", "-A")
        message = git_sync.describe_staged_changes(str(self.repo))
        self.assertIn("  SKILL.md", message)
        self.assertIn("  principles/code-decides.md", message)

    def test_subject_stays_within_the_console_width(self):
        for i in range(6):
            self.write(f"hardware/super-long-skill-name-number-{i}/scripts/x.py")
        self.run("add", "-A")
        subject = git_sync.describe_staged_changes(str(self.repo)).splitlines()[0]
        self.assertLessEqual(len(subject), git_sync.MAX_SUBJECT)

    def test_no_staged_changes_falls_back(self):
        self.assertEqual(
            git_sync.describe_staged_changes(str(self.repo)).splitlines()[0],
            "chore: sync working tree",
        )

    def test_root_files_are_grouped_under_a_name_not_a_filename(self):
        self.write("a.txt")
        self.write("pyproject.toml")
        self.run("add", "-A")
        body = git_sync.describe_staged_changes(str(self.repo))
        self.assertIn("root (2 files", body)
        self.assertNotIn("a.txt (2 files", body)

    def test_root_scope_is_named_not_parenthesised_twice(self):
        self.write("a.txt")
        self.write("b.txt")
        self.run("add", "-A")
        subject = git_sync.describe_staged_changes(str(self.repo)).splitlines()[0]
        self.assertEqual(subject, "chore(root): 2 files (+2/-0)")

    def test_guarded_commit_derives_when_message_is_omitted(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        git_sync.guarded_commit(str(self.repo), None)
        subject = self.run("log", "-1", "--format=%s").stdout.strip()
        self.assertEqual(subject, "chore(kem-thought): SKILL.md (+1/-0)")

    def test_explicit_message_becomes_body_under_auto_subject(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        git_sync.guarded_commit(str(self.repo), "docs(kem-thought): state the convention")
        subject = self.run("log", "-1", "--format=%s").stdout.strip()
        body = self.run("log", "-1", "--format=%b").stdout.strip()
        self.assertEqual(subject, "chore(kem-thought): SKILL.md (+1/-0)")
        self.assertIn("docs(kem-thought): state the convention", body)

    def test_explicit_message_keeps_the_file_manifest_below_it(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        self.write("glitch-cat/kem-thought/principles/code-decides.md")
        git_sync.guarded_commit(str(self.repo), "docs(kem-thought): state the convention")
        body = self.run("log", "-1", "--format=%b").stdout.strip()
        prose_at = body.find("docs(kem-thought): state the convention")
        manifest_at = body.find("kem-thought (2 files")
        self.assertNotEqual(prose_at, -1, body)
        self.assertNotEqual(manifest_at, -1, body)
        self.assertLess(prose_at, manifest_at, "the manifest belongs under the prose")
        self.assertIn("  principles/code-decides.md", body)

    def test_manifest_is_not_duplicated_when_the_message_already_has_it(self):
        self.write("glitch-cat/kem-thought/SKILL.md")
        self.run("add", "-A")
        manifest = git_sync.staged_change_body(str(self.repo))
        self.assertIn("kem-thought (1 file", manifest)
        git_sync.guarded_commit(str(self.repo), "docs: keep this list\n\n" + manifest)
        body = self.run("log", "-1", "--format=%b").stdout.strip()
        self.assertEqual(body.count("kem-thought (1 file"), 1, body)

    def test_secret_in_a_new_directory_is_blocked(self):
        self.write("academic/new-skill/scripts/config.py", TestPublicationGuard.FAKE_PAT + "\n")
        result = git_sync.guarded_commit(str(self.repo), None)
        self.assertEqual(len(result["blocked"]), 1)
        self.assertEqual(result["committed"], [])

    def test_blocked_commit_exits_nonzero(self):
        self.write("academic/new-skill/scripts/config.py", TestPublicationGuard.FAKE_PAT + "\n")
        proc = subprocess.run(
            [sys.executable, str(HERE / "git_sync.py"), "guarded-commit", "--repo", str(self.repo)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)


class TestGate(unittest.TestCase):
    def test_gate_runs_on_a_python_project_without_crashing(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        previous = Path.cwd()
        os.chdir(tmp)
        self.addCleanup(os.chdir, previous)
        self.assertEqual(git_sync.stage4_gate(), [])


class TestProtectedPush(unittest.TestCase):
    def test_refuses_a_protected_branch_without_a_tty(self):
        with patch("sys.stdin") as fake_stdin:
            fake_stdin.isatty.return_value = False
            with self.assertRaises(SystemExit):
                git_sync.stage6_push("main", has_upstream=True, auto_yes=False)


class TestCommitComposition(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        run = lambda *a: subprocess.run(["git", "-C", str(self.repo)] + list(a),
                                        capture_output=True, text=True, check=True)
        run("init", "-b", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        (self.repo / "glitch-cat" / "kem-thought").mkdir(parents=True)
        (self.repo / "glitch-cat" / "kem-thought" / "SKILL.md").write_text("x\n", encoding="utf-8")
        run("add", "-A")

    def test_compose_puts_the_manifest_under_the_prose(self):
        message = git_sync.compose_message(str(self.repo), "feat: say why this moved")
        self.assertEqual(message.splitlines()[0], "chore(kem-thought): SKILL.md (+1/-0)")
        self.assertLess(message.find("feat: say why this moved"),
                        message.find("kem-thought (1 file"))

    def test_compose_without_prose_is_subject_and_manifest(self):
        message = git_sync.compose_message(str(self.repo), None)
        self.assertEqual(message, git_sync.describe_staged_changes(str(self.repo)))


if __name__ == "__main__":
    unittest.main()
