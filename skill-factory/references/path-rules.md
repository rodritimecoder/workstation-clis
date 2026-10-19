# Path rules

A skill body must not hardcode a harness path.

## The problem

The same skill is mirrored into three harness directories:

```
~/.gemini/config/skills/<skill>/
~/.config/opencode/skills/<skill>/
~/.pi/agent/skills/<skill>/
```

A body that says `~/.gemini/config/skills/hybrid-browser/scripts/run.sh`
resolves in all three — but only because `sync-skills` copies the whole
tree. It is wrong documentation that happens to work, and it breaks the
moment the skill is used from anywhere else, or from a checkout, or from a
container.

**Nine skills in this collection do it:** `agent-reach`, `canvas-cli`,
`edstem-cli`, `github-architect`, `hybrid-browser`, `markitdown-cli`,
`video-miner`, `worktree-harness`, `zoom-recorder`.

## The fix, in order of preference

### 1. Use the catalog

The skill's tools are already in the catalog, with resolved absolute paths
and machine-readable contracts. Referencing a tool by id is portable by
construction:

```bash
omnicli invoke zoom-recorder/scripts/zoom_download -- --url "$URL"
```

This is also better documentation: it names the *tool*, and the tool's
contract is one call away.

### 2. Use a skill-relative path

When the command genuinely is a file inside the skill, and the agent is
running from the skill directory:

```bash
scripts/run.sh --url "$URL"
```

### 3. Use a `~/.local/bin` shim

When the skill ships a shim on the PATH:

```bash
tailscale-ops check-port "$HOST" 8080
```

## What the gate checks

`audit.py` flags any occurrence of:

```
~/.gemini/config/skills/
~/.config/opencode/skills/
~/.pi/agent/skills/
```

and treats it as a failure, not a warning — because a body that hardcodes a
harness path is wrong in one of the three harnesses the moment the tree
stops being mirrored, and the cost of finding out then is an agent
executing a path that does not exist.

## A subtlety worth keeping

A skill that is *about* a specific harness — one that manages harness
configuration, or documents a harness's own layout — may legitimately name
harness paths. In that case the path is the subject matter, not an
accident. The gate cannot tell the difference, so if it flags such a
skill, say so rather than silently rewriting it.
