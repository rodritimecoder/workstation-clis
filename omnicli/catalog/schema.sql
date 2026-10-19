-- omnicli catalog schema
--
-- The control plane. One SQLite database that indexes every skill, every
-- script, and every reference doc on the workstation so that an agent can
-- find the right tool from a natural-language intent without loading every
-- SKILL.md into its context window.

PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------- skills
CREATE TABLE IF NOT EXISTS skills (
    name        TEXT PRIMARY KEY,   -- frontmatter name (may differ from dir)
    dir_name    TEXT NOT NULL,      -- directory name on disk
    path        TEXT NOT NULL,
    md_path     TEXT,
    description TEXT DEFAULT '',
    status      TEXT DEFAULT 'active',   -- active | glitch-cat | archived
    cli         TEXT,               -- resolved ~/.local/bin shim, if any
    aliases     TEXT DEFAULT '[]',  -- JSON list of hand-curated synonyms
    tags        TEXT DEFAULT '[]',  -- JSON list
    tools       INTEGER DEFAULT 0,
    indexed_at  REAL
);

-- ----------------------------------------------------------------- tools
-- The unified tool registry. Every script, CLI shim, and local inference
-- endpoint is a "tool" with a machine-readable contract, so that `describe`
-- can hand the agent exactly one tool's input contract at a time.
CREATE TABLE IF NOT EXISTS tools (
    id       TEXT PRIMARY KEY,   -- "<skill>/<relpath-no-ext>" or "<...>:<subcmd>"
    skill    TEXT NOT NULL,
    kind     TEXT NOT NULL,      -- script | cli | endpoint
    summary  TEXT DEFAULT '',
    path     TEXT,
    argv     TEXT DEFAULT '[]',  -- JSON argv template
    contract TEXT DEFAULT '{}',  -- JSON: {usage, flags, positionals, subcommands}
    parent   TEXT,               -- for subcommand tools, the parent tool id
    indexed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_tools_skill ON tools(skill);
CREATE INDEX IF NOT EXISTS idx_tools_kind  ON tools(kind);

-- ------------------------------------------------------------------ docs
-- FTS5 index over chunked documentation. Chunking is what kills the
-- "long generic document wins" failure mode: BM25 normalises for length
-- within a chunk, and a 50KB meta-doc becomes 20 comparable sections
-- instead of one unbeatable blob.
--
-- `aliases` is a separate, independently weighted column. A hand-curated
-- alias ("podcast" -> audiocpp) is deliberate author intent that says "route
-- this vocabulary here". That is a different kind of evidence from prose
-- that happens to contain the word, and it must not be out-voted by
-- incidental matches spread across a large document.
CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
    skill  UNINDEXED,   -- owning skill name
    kind   UNINDEXED,   -- skill | body | script | reference
    title,              -- section heading / script name
    path,               -- source file
    body,               -- chunk text
    aliases,            -- curated synonym list (high weight)
    tokenize = 'porter unicode61'
);

-- ------------------------------------------------------------------ meta
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
