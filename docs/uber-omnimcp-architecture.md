# Uber OmniMCP & Code Mode Protocol Architecture

Solving Skill Shadowing, Tool Bloat, and Context Degradation across 28+ Workstation Skills.

---

## 1. The Core Problem: Why Installing More Skills Breaks Agents

Conventional agent harnesses claim that "Progressive Disclosure" (injecting only a 100-token `name` + `description` at turn 0 and deferring the 5,000-token `SKILL.md` body until selected) makes installing dozens or hundreds of skills "free."

Recent empirical research proves this is false—not primarily because of token count, but because of **Selection Failure (Shadowing)** and **Blind Routing**:

| Study / Source | Scale | Key Finding |
| :--- | :--- | :--- |
| **Databricks "Skill Shadowing" Study (May 2026)** | 2,500 runs scaling from Oracle skills $\rightarrow$ 52 $\rightarrow$ 102 $\rightarrow$ 202 skills | Pass rate dropped **21 percentage points**. Context overhead was only ~6 pts; **Shadowing (picking wrong or picking nothing)** accounted for **2/3 of the total failure**. |
| **The "Abandonment" Phenomenon** | Oracle vs. 202-skill library | Correct skill selection dropped from **88% down to 52.6%**. Total abandonment (agent stares at 200 descriptions, recognizes none, and writes from scratch) surged from **12% to 38.5%**. |
| **SkillRouter Attention Analysis (Mar 2026)** | ~80,000 skills | Routing signal lives in: **Name = 7.3%**, **Description = 1.0%**, **Body (`SKILL.md` content) = 91.7%**. Stripping bodies drops routing accuracy by **37–44 points**. |
| **Public GitHub Skill Audit (Jul 2026)** | 3.8M skill files across 282k repos | **26.4%** of public skills ship with **zero routing description**, and ~50% are verbatim duplicates. |
| **GitHub Copilot Tool Trim (Nov 2025)** | Trimmed tools from 40 down to 13 + embedding search | SWE-bench success rates rose **2–5 percentage points**; latency dropped **400ms**. |

> **Core Takeaway:** Retrieval beats installation. A static prompt shelf of >30 tools degrades LLM reasoning. The agent router must search across the **full body content** of skills/tools rather than forcing the model to evaluate 30+ frontmatter descriptions on turn 0.

---

## 2. Uber's Architecture: OmniMCP & `aifx` Code Mode

Uber operates **5,000+ MCP tools across 800+ internal servers**. Exposing them via standard MCP `list_tools` overflows context and triggers immediate shadowing.

Uber resolved this through two complementary patterns implemented on this workstation:
1. **OmniMCP (The 4 Meta-Tools)** for JSON-RPC tool-calling agents.
2. **`aifx` Code Mode (`skills-hub`)** for terminal/shell harnesses (`agy`, Pi Agent).

```
[ AI Agent (Antigravity / Pi / Subagent) ]
        │
        ├── Interface A: OmniMCP (4 Meta-Tools Only)
        └── Interface B: "Code Mode" via `skills-hub` CLI (search | inspect | run)
        │
        ▼
[ skills-hub Gateway (Data Plane) & Catalog Index (Control Plane) ]
   ├── Full-Body BM25 / Vector Search (91.7% signal recovery)
   ├── Dynamic Tool Schema Extraction (1 tool at a time)
   ├── Response Projection (--project / --jq field stripping)
   └── Disk Buffering (--out /tmp/... to keep context lean)
```

---

## 3. Pattern A: The 4 Meta-Tools (`OmniMCP`)

Instead of loading 5,000 tools into the system prompt, the agent receives **only 4 tiny meta-tools** (~400 tokens total):

| Step | Meta-Tool Name | Input Argument | What Enters the Context Window |
| :--- | :--- | :--- | :--- |
| **1** | `discover_server` | Natural language `intent` | Matching skill category names (no schemas). |
| **2** | `discover_tools` | `skill_name` from Step 1 | Tool names + concise descriptions inside that skill. |
| **3** | `get_tool_schema` | `skill_name` + `tool_name` | The exact input contract for **that 1 tool only**. |
| **4** | `invoke_tool` | `tool_name`, `arguments`, `projection` | The projected, filtered execution result. |

### Why This Eliminates Shadowing
- **Zero Startup Freight:** Model starts turn 0 with ~400 tokens instead of 150,000 tokens.
- **Full-Body Search at Step 1:** By indexing the markdown bodies and docstrings, search captures the 91.7% signal that frontmatter descriptions drop.
- **Single Active Schema:** At most 1 tool schema exists in context at any turn.

---

## 4. Pattern B: `aifx` Code Mode & Output Bloat Prevention

Even with small tool definitions, a single tool returning a 100 KB JSON payload will pollute agent reasoning. We pair two architectural defenses:

### 4.1 Response Projection (Pre-Flight Field Filtering)
The caller specifies only the fields the model actually requires before execution:
```bash
# Gateway strips unrequested fields before LLM sees the output
skills-hub run worktree-harness status --project "run_id,active_workers,claims"
```

### 4.2 Disk Buffering (Keeping Large Payloads on Disk)
For shell agents, outputs write to disk buffers, and the agent uses `grep` or `jq` to pull only matching lines into context:
```bash
# Output stays on disk; context takes 0 tokens
skills-hub run cdp-browser --url "http://localhost:3000" --out /tmp/trace.json

# Read only relevant errors into context
jq '{errors: .console_errors, status: .http_status}' /tmp/trace.json
```
*Anthropic's benchmark of this pattern demonstrated a **98.7% context token reduction** (from 150,000 down to 2,000 tokens).*

---

## 5. Workstation CLI Mapping

| Command | Action |
| :--- | :--- |
| `skills-hub search "<intent>"` | Full-body search across all 28+ workstation skills |
| `skills-hub tools <skill>` | List executable tools and scripts within winning skill |
| `skills-hub inspect <skill>` | View exact usage contract and rubric on demand |
| `skills-hub run <skill> [args] [--project] [--out]` | Execute tool with response projection and disk buffering |
