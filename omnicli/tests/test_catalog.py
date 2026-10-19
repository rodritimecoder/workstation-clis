"""Unit tests for the omnicli catalog and the CLI's core guarantees.

Run:
    python3 tests/test_catalog.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from catalog import builder, registry, search, textutil  # noqa: E402
from omnicli import _cap, parse_invoke_args  # noqa: E402


class TestTextUtil(unittest.TestCase):
    def test_latin_tokens_stay_whole(self):
        self.assertEqual(textutil.tokenize("transcribe a zoom lecture"),
                         ["transcribe", "a", "zoom", "lecture"])

    def test_cjk_splits_into_bigrams(self):
        self.assertEqual(textutil.tokenize("调研"), ["调研"])

    def test_long_cjk_run_becomes_bigrams(self):
        toks = textutil.tokenize("调研一下这个话题")
        self.assertEqual(toks, ["调研", "研一", "一下", "下这", "这个", "个话", "话题"])

    def test_cjk_expand_adds_bigrams(self):
        out = textutil.expand_cjk("调研一下")
        self.assertIn("调研", out)
        self.assertIn("研一", out)
        self.assertIn("一下", out)

    def test_latin_text_unchanged_by_expand(self):
        self.assertEqual(textutil.expand_cjk("hello world"), "hello world")


class TestFrontmatter(unittest.TestCase):
    def test_plain_scalars(self):
        name, desc = registry.parse_frontmatter("---\nname: foo\ndescription: bar baz\n---\nbody")
        self.assertEqual(name, "foo")
        self.assertEqual(desc, "bar baz")

    def test_folded_block(self):
        md = "---\nname: foo\ndescription: >\n  one two\n  three four\n---\nbody"
        name, desc = registry.parse_frontmatter(md)
        self.assertEqual(name, "foo")
        self.assertEqual(desc, "one two three four")

    def test_literal_block(self):
        md = "---\nname: foo\ndescription: |\n  line one\n  line two\n---\nbody"
        _, desc = registry.parse_frontmatter(md)
        self.assertIn("line one", desc)
        self.assertIn("line two", desc)

    def test_quoted_value(self):
        name, desc = registry.parse_frontmatter('---\nname: "foo"\ndescription: "a b c"\n---\n')
        self.assertEqual(name, "foo")
        self.assertEqual(desc, "a b c")

    def test_missing_frontmatter(self):
        name, desc = registry.parse_frontmatter("no frontmatter here")
        self.assertEqual(name, "")
        self.assertEqual(desc, "")


class TestContractExtraction(unittest.TestCase):
    def test_parses_flags_and_subcommands(self):
        help_text = (
            "usage: tool.py [-h] [--json] [--port PORT]\n"
            "       {asr,tts,align} ...\n\n"
            "positional arguments:\n"
            "    {asr,tts,align}\n"
            "                        Available subcommands\n"
            "    asr\n"
            "                        Speech to text\n"
            "    tts\n"
            "                        Text to speech\n"
        )
        c = registry.parse_help_contract(help_text)
        self.assertIn("--json", c["flags"])
        self.assertIn("--port", c["flags"])
        names = [s["name"] for s in c["subcommands"]]
        self.assertEqual(names, ["asr", "tts", "align"])
        self.assertEqual(c["subcommands"][0]["summary"], "Speech to text")

    def test_empty_help_is_safe(self):
        c = registry.parse_help_contract("")
        self.assertEqual(c["flags"], [])
        self.assertEqual(c["subcommands"], [])


class TestInvokeParsing(unittest.TestCase):
    def test_tool_id_and_passthrough(self):
        tool_id, opts, args = parse_invoke_args(["local/decide", "--help", "--port", "80"])
        self.assertEqual(tool_id, "local/decide")
        self.assertEqual(args, ["--help", "--port", "80"])
        self.assertFalse(opts["json"])

    def test_gateway_flags_are_extracted(self):
        tool_id, opts, args = parse_invoke_args(
            ["local/llm", "--omni-buffer", "/tmp/x", "--omni-max-bytes", "500", "--omni-json"])
        self.assertEqual(tool_id, "local/llm")
        self.assertEqual(opts["buffer"], "/tmp/x")
        self.assertEqual(opts["max_bytes"], 500)
        self.assertTrue(opts["json"])
        self.assertEqual(args, [])

    def test_tool_out_flag_is_not_stolen(self):
        _, opts, args = parse_invoke_args(["tool", "--out", "/tmp/tool-owned"])
        self.assertIsNone(opts["buffer"])
        self.assertEqual(args, ["--out", "/tmp/tool-owned"])

    def test_double_dash_forces_split(self):
        tool_id, opts, args = parse_invoke_args(["tool", "--omni-json", "--", "--omni-json"])
        self.assertTrue(opts["json"])
        self.assertEqual(args, ["--omni-json"])

    def test_missing_tool_id(self):
        tool_id, _, _ = parse_invoke_args(["--omni-json"])
        self.assertIsNone(tool_id)


class TestOutputCap(unittest.TestCase):
    def test_cap_is_never_exceeded(self):
        for cap in (10, 50, 100, 200, 500, 1000, 8000, 100000):
            out, truncated, total = _cap("X" * 50000, cap)
            self.assertLessEqual(len(out.encode()), cap,
                                 f"cap {cap} exceeded by {len(out.encode())}")
            if cap < 50000:
                self.assertTrue(truncated, f"cap {cap} should have truncated")
            self.assertEqual(total, 50000)

    def test_payload_within_cap_is_untouched(self):
        out, truncated, total = _cap("short", 8000)
        self.assertEqual(out, "short")
        self.assertFalse(truncated)
        self.assertEqual(total, 5)


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = builder.connect()
        builder.ensure_built(cls.con, progress=False)

    def test_catalog_is_populated(self):
        skills = self.con.execute("SELECT count(*) c FROM skills").fetchone()["c"]
        tools = self.con.execute("SELECT count(*) c FROM tools").fetchone()["c"]
        docs = self.con.execute("SELECT count(*) c FROM docs").fetchone()["c"]
        self.assertGreater(skills, 20)
        self.assertGreater(tools, 100)
        self.assertGreater(docs, 500)

    def test_every_skill_has_a_doc(self):
        missing = self.con.execute(
            "SELECT s.name FROM skills s WHERE NOT EXISTS "
            "(SELECT 1 FROM docs d WHERE d.skill = s.name)"
        ).fetchall()
        self.assertEqual([m["name"] for m in missing], [])

    def test_local_endpoints_are_tools(self):
        for tid in ("local/llm", "local/ocr", "local/decide", "local/asr"):
            row = self.con.execute("SELECT 1 FROM tools WHERE id = ?", (tid,)).fetchone()
            self.assertIsNotNone(row, f"missing endpoint tool {tid}")

    def test_scripts_have_contracts(self):
        """Most script tools must expose a usage contract.

        A minority legitimately do not: shell wrappers with no usage
        function, hook and library scripts, and the MCP stdio server, which
        has no argparse by design. Those are recorded as empty contracts
        rather than garbage.
        """
        rows = self.con.execute(
            "SELECT id, contract FROM tools WHERE kind = 'script'"
        ).fetchall()
        self.assertGreater(len(rows), 20)
        missing = [r["id"] for r in rows if not json.loads(r["contract"] or "{}").get("usage")]
        self.assertLess(len(missing), len(rows) * 0.30,
                        f"too many scripts without a usage contract: {missing}")

    def test_contracts_are_never_garbage(self):
        """A contract's help text must look like usage output."""
        rows = self.con.execute(
            "SELECT id, contract FROM tools WHERE kind = 'script'"
        ).fetchall()
        for r in rows:
            c = json.loads(r["contract"] or "{}")
            if c.get("help"):
                self.assertIn("usage:", c["help"].lower(),
                              f"{r['id']} stored non-usage output as a contract")

    def test_key_tools_have_contracts(self):
        for tid in ("audiocpp/scripts/audiocpp_cli", "ocr/ocr", "canvas-cli/scripts/canvas_cli"):
            row = self.con.execute(
                "SELECT contract FROM tools WHERE id = ?", (tid,)).fetchone()
            if row is None:
                continue
            c = json.loads(row["contract"] or "{}")
            self.assertTrue(c.get("usage"), f"{tid} has no usage contract")

    def test_subcommands_are_addressable_tools(self):
        row = self.con.execute(
            "SELECT id FROM tools WHERE id LIKE 'audiocpp/scripts/audiocpp_cli:%'"
        ).fetchall()
        self.assertGreater(len(row), 0, "expected audiocpp subcommand tools")

    def test_router_body_is_not_indexed(self):
        """The router's own prose must not compete with the skills it routes to."""
        n = self.con.execute(
            "SELECT count(*) c FROM docs WHERE skill = 'omnicli' AND kind = 'body'"
        ).fetchone()["c"]
        self.assertEqual(n, 0)

    def test_aliases_are_curated_metadata(self):
        row = self.con.execute(
            "SELECT aliases FROM skills WHERE name = 'audiocpp'").fetchone()
        aliases = json.loads(row["aliases"])
        self.assertIn("podcast", aliases)


class TestContractCache(unittest.TestCase):
    """The contract cache makes rebuilds incremental.

    Without it every rebuild re-runs --help on sixty-odd scripts, which is
    the difference between 130ms and 3.2 seconds.
    """

    @classmethod
    def setUpClass(cls):
        cls.con = builder.connect()

    def test_cache_roundtrip(self):
        builder._store_contract(self.con, "/tmp/fake.py", 12345, "/usr/bin/python3",
                                {"usage": "x", "flags": ["--a"], "positionals": [],
                                 "subcommands": [{"name": "s"}], "help": "usage: x"})
        got = builder._cached_contract(self.con, "/tmp/fake.py", 12345, "/usr/bin/python3")
        self.assertIsNotNone(got)
        self.assertEqual(got["usage"], "x")
        self.assertEqual(got["subcommands"][0]["name"], "s")

    def test_cache_invalidated_by_mtime(self):
        builder._store_contract(self.con, "/tmp/fake2.py", 1, "", {"usage": "old"})
        self.assertIsNone(builder._cached_contract(self.con, "/tmp/fake2.py", 2, ""))
        self.assertIsNone(builder._cached_contract(self.con, "/tmp/fake2.py", 1, "/other"))

    def test_cache_survives_a_rebuild(self):
        """A rebuild must not lose subcommand tools to the cache.

        This is the regression that a dropped `contract = cached` assignment
        caused: the rebuild succeeded, the tool count collapsed, and nothing
        errored.

        The rebuild runs against a temporary database. Rebuilding the live
        catalog here would mean running the test suite mutates shared state,
        and it races with any sync that is copying skills around at the
        time.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            con = builder.connect(Path(tmp) / "test-catalog.db")
            try:
                builder.build(con, progress=False)
                first = con.execute(
                    "SELECT count(*) AS c FROM tools WHERE kind = 'subcommand'"
                ).fetchone()["c"]
                self.assertGreater(first, 100, "expected subcommand tools in the catalog")

                # Second build: the contracts now come from the cache.
                builder.build(con, progress=False)
                second = con.execute(
                    "SELECT count(*) AS c FROM tools WHERE kind = 'subcommand'"
                ).fetchone()["c"]
                self.assertEqual(second, first,
                                 f"rebuild lost subcommand tools: {first} -> {second}")
            finally:
                con.close()

    def test_cached_contracts_keep_their_subcommands(self):
        row = self.con.execute(
            "SELECT contract FROM tools WHERE id = 'audiocpp/scripts/audiocpp_cli'"
        ).fetchone()
        contract = json.loads(row["contract"])
        self.assertGreaterEqual(len(contract.get("subcommands", [])), 5,
                                "audiocpp_cli should expose its subcommands")


class TestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = builder.connect()
        builder.ensure_built(cls.con, progress=False)

    def _top(self, query, n=1):
        res = search.search(self.con, query, limit=n, rerank_enabled=False)
        return [r["skill"] for r in res["results"]]

    def test_alias_bridges_vocabulary_gap(self):
        self.assertEqual(self._top("turn a recorded podcast into readable text"), ["audiocpp"])

    def test_generic_metadoc_does_not_hijack(self):
        top = self._top("turn a recorded podcast into readable text", n=3)
        self.assertNotIn("icm-architect", top[:1])

    def test_cjk_query_routes(self):
        top = self._top("调研一下这个话题在网上的讨论", n=3)
        self.assertIn("agent-reach", top)

    def test_stopword_only_query(self):
        res = search.search(self.con, "the a of", limit=3)
        self.assertEqual(res["results"], [])

    def test_empty_query(self):
        res = search.search(self.con, "", limit=3)
        self.assertEqual(res["results"], [])

    def test_matches_are_ordered_by_score(self):
        res = search.search(self.con, "code review before committing", limit=5)
        scores = [r["score"] for r in res["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_result_is_json_serialisable(self):
        """`omnicli search --json` must not raise.

        A working set left in the result dict (a set of matched tokens) made
        the JSON encoder raise a TypeError, and nothing caught it: the
        library tests only read individual fields.
        """
        res = search.search(self.con, "click a button on a web page", limit=3)
        text = json.dumps(res)
        self.assertIn("results", json.loads(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
