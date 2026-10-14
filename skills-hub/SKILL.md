---
name: skills-hub
description: >
  Unified meta-tool discovery and execution layer for 28+ agent skills. Lets agents
  search skills by intent, inspect exact usage runbooks, and execute commands dynamically
  without bloating the context window with individual tool schemas.
---

# Skills Hub (`skills-hub`)

The Meta-Tool Discovery and Execution Gateway for your agent environment. Instead of injecting 28+ separate tool schemas into an LLM context, `skills-hub` exposes 3 universal operations:

1. **`search`**: Find relevant skills by natural language intent (e.g. "transcribe lecture", "audit git repo").
2. **`inspect`**: Read the authoritative runbook, CLI flags, and parameter schemas for a chosen skill.
3. **`run`**: Execute the skill's CLI tool directly and capture the output.

---

## 🚀 Quick Usage

### 1. Search for Skills by Intent
```bash
skills-hub search "transcribe audio"
skills-hub search "git secrets and audit"
skills-hub search "ocr text extraction"
```

### 2. Inspect a Skill's Full Usage & Commands
```bash
skills-hub inspect audiocpp-asr
skills-hub inspect github-architect
skills-hub inspect litellm-vram-switcher
```

### 3. Run a Skill Dynamically
```bash
skills-hub run tailscale-ops peers
skills-hub run github-architect audit .
skills-hub run litellm-vram-switcher status
```

### 4. List All Registered Skills
```bash
skills-hub list
```
