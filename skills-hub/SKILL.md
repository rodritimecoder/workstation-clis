---
name: skills-hub
description: >
  Unified Uber OmniMCP and aifx Late-Binding Gateway for 28+ agent skills. Eliminates
  skill shadowing and tool bloat via a 4-step discovery funnel (discover -> tools -> schema -> invoke),
  full-body search (91.7% routing signal), pre-flight response projection (--project, --jq),
  and disk buffering (--out).
---

# Skills Hub — Uber OmniMCP & `aifx` Gateway (`skills-hub`)

`skills-hub` is the primary late-binding execution gateway for all agent skills on this workstation. It implements the **Uber OmniMCP & `aifx` Protocol** to solve the dual crises of **Skill Shadowing** (where loading 30+ skills drops accuracy by 21 points) and **Output Bloat** (where unprojected JSON destroys context).

---

## 🏛️ The 4-Step Funnel (Uber OmniMCP Pattern)

Instead of dumping 30+ skill definitions into the agent's system prompt at startup, the agent uses a 4-step progressive funnel:

| Step | CLI Command | Purpose | Context Freight |
|---|---|---|---|
| **1. Discover** | `skills-hub search "<intent>"` | Searches full `SKILL.md` bodies & scripts for winning skills. | ~50 tokens |
| **2. Tools** | `skills-hub tools <skill>` | Lists executable scripts and utilities inside the winning skill. | ~20 tokens |
| **3. Schema** | `skills-hub inspect <skill>` | Loads the exact usage contract and rubric for **that 1 skill only**. | ~300 tokens |
| **4. Invoke** | `skills-hub run <skill> [args] [--out / --project]` | Executes the tool with response projection & disk buffering. | Filtered / Lean |

---

## 🛡️ Response Projection & Disk Buffering

To prevent a single tool response from dumping a 50 KB payload into the agent's context window:

### 1. Pre-Flight Field Projection (`--project` or `--jq`)
Filter fields before output enters the LLM context:
```bash
# Project specific keys from JSON output
skills-hub run canvas-cli courses --project "id,name,course_code"

# Filter with JQ syntax
skills-hub run github-architect list --jq '.[].name'
```

### 2. Disk Buffering (`--out`)
Stream the heavy raw execution trace to a file on disk, returning only an exit status receipt to the LLM:
```bash
skills-hub run video-miner videomine.py "https://..." --out /tmp/video_extract.json
```
The agent then uses `grep` or `jq` on `/tmp/video_extract.json` on-demand.

---

## CLI Reference

```bash
# Search by intent across all 28+ skills in the upstream vault
skills-hub search "transcribe lecture video"
skills-hub search "canvas assignments"
skills-hub search "review git diff for memory leaks"

# Step 2: List internal tools of a winning skill
skills-hub tools audiocpp-asr

# Step 3: Read single skill documentation
skills-hub inspect audiocpp-asr

# Step 4: Run dynamically with disk buffering
skills-hub run audiocpp-asr asr.py ./lecture.mp3 --out /tmp/transcript.json
```
