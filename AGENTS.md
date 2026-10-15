# AI Inference & Models Volume (`/run/media/rodri/AI`)

Authoritative catalog of local AI inference engines, model weights, port bindings, and agent skills on this machine.

**Host Hardware:** Dual AMD Radeon RX 9060 XT GPUs (Navi 44, Vulkan + ROCm).

---

## Active Ports & Inference Services

Always check health before launching (`curl -s http://127.0.0.1:<port>/health`).

| Port | Service | Default Model | Launcher | Health Check | Primary Skill Consumer |
|---|---|---|---|---|---|
| `:8080` | `llama-server` (Vulkan) | `Qwen3.6-35B-A3B Uncensored Genesis` | `sh/luffy_nothink.sh` | `curl -s http://127.0.0.1:8080/health` | Main Coding & Reasoning Agent |
| `:8081` | `audio.cpp` (Vulkan) | `nemotron-asr`, `kokoro-v1.0`, `qwen3-forced-aligner` | `audio-v0.9.0-bin-ubuntu-x64-vulkan/run-audiocpp.sh` | `curl -s http://127.0.0.1:8081/health` | `audiocpp-asr`, `video-miner` |
| `:8083` | `llama-server` (Vulkan) | `imajev-4b-Q4_K_M` + `mmproj` | `sh/imajev-4b.sh` | `curl -s http://127.0.0.1:8083/health` | `jev-cli`, `video-miner` |
| `:8084` | `crispembed-server` | `CrispEmbed Scene Text (DBNet + PARSeq)` | `sh/crispembed-ocr.sh` | `curl -s http://127.0.0.1:8084/health` | `ocr-cli` |
| `:8085` | `llama-server` (Vulkan) | `LightOnOCR-3-1B` | `sh/lighton-ocr.sh` | `curl -s http://127.0.0.1:8085/health` | `ocr-cli`, `video-miner` |
| `:8090` | `jpt-engine` | `jpt-4b.Q4_K_M` + `mmproj` | `sh/jpt-4b/` | `curl -s http://127.0.0.1:8090/health` | `jev-cli` |

---

## Unified Gateway & Skills Dispatch (`skills-hub`)

All 34+ agent skills in `/run/media/rodri/AI/skills/` are unified under the late-binding **`skills-hub`** gateway to eliminate skill shadowing, static table drift, and context bloat.

### 1. Local Model Server Consumers
The raw inference daemons listed in the port matrix above are consumed by dedicated CLI skills, executable directly or through `skills-hub run`:

| Daemon Port | Service & Engine | Primary Consumer Skill | Unified `skills-hub` Invocation |
|---|---|---|---|
| `:8080` | Genesis Qwen35B (Coding/Reasoning) | `eval-router`, `graph-memory` | `skills-hub run eval-router router.py exec "<prompt>"` |
| `:8081` | `audio.cpp` (Nemotron 3.5 ASR) | `audiocpp-asr`, `video-miner` | `skills-hub run audiocpp-asr asr.py transcribe <audio>` |
| `:8083` | `llama-server` (Imajev-4B Decision) | `jev-cli`, `eval-router`, `video-miner` | `skills-hub run jev-cli decide.py <state> <question> <options>` |
| `:8084` | `crispembed-server` (Scene Text) | `ocr-cli` | `skills-hub run ocr-cli ocr.py <image> --model crispembed` |
| `:8085` | `llama-server` (LightOnOCR-3-1B) | `ocr-cli`, `video-miner` | `skills-hub run ocr-cli ocr.py <image-or-pdf>` |
| `:8090` | `jpt-engine` (JPT-4B System One) | `jev-cli` | `skills-hub run jev-cli decide.py --model jpt ...` |

### 2. The 4-Step Late-Binding Funnel (No Static Table Redundancy)
Never dump static skill lists into the prompt or hardcode paths. Use the dynamic discovery funnel:
- **Discover:** `skills-hub search "<intent>"` (searches all 34+ skills via full-body index)
- **Inspect Tools:** `skills-hub tools <skill>` (lists available executable scripts)
- **Read Contract:** `skills-hub inspect <skill>` (loads the exact YAML contract for that 1 skill only)
- **Invoke with Projection:** `skills-hub run <skill> <script> [args] [--out / --project]` (runs with disk buffering)
- **Full Live Vault:** `skills-hub list` (lists all 34+ skills dynamically from upstream)

---

## Key Directories

- **`skills/`**: Canonical upstream directory of agent skills, CLI tools, and ICM templates.
- **`models/`**: Central storage for all GGUF weights, vision projectors (`mmproj`), and audio models. See [models/CATALOG.md](models/CATALOG.md).
- **`sh/`**: Production Linux launcher scripts for servers, benchmarks, and voice pipelines. See [sh/README.md](sh/README.md).
- **`bat/`**: Windows batch launchers for dual-boot environment parity.
- **`llama.cpp/`**: Local build (`build/bin/llama-server`). Contains the `head_dim` patch in `src/models/qwen2vl.cpp` required for NaviDC-OCR.
- **`audio-v0.9.0-bin-ubuntu-x64-vulkan/`**: Native Vulkan binary distribution of `audio.cpp` (`audiocpp_cli`).
- **`ROCmFPX/`**: ROCm FP4/FPX kernels and quantizations.

---

## Hierarchy of Authority & Source of Truth

This directory (`/run/media/rodri/AI`) is the **canonical source of truth** for all local AI hardware configurations, model weights, inference daemons, launcher scripts, and skills on this machine.

1. **Upstream First:** Whenever updating server ports, GPU offload flags, model quants, shared inference utilities, or skill scripts, make the edit in `/run/media/rodri/AI/` first.
2. **Harness Propagation:** Downstream harnesses are local consumers:
   - Antigravity / Gemini CLI: `~/.gemini/config/skills/`
   - Pi Agent: `~/.pi/agent/skills/`
3. **Sync & GitHub Push:** When updating a skill upstream, propagate to downstream harnesses, workstation-clis, and push to GitHub:
   ```bash
   sync-skills --push
   ```
4. **No Drift:** Never edit a launcher script or skill in a downstream harness without committing the change upstream here.

---

## Invariants & Rules for Agents

1. **Verify before restarting:** Never stop or kill a running server without checking if another process or user is using it. Always test `curl -s http://127.0.0.1:<port>/health` first.
2. **NaviDC head_dim restriction:** Stock upstream `llama-server` **cannot** load NaviDC-OCR GGUFs (fails on `head_dim=128` vs `64`). Always use `/run/media/rodri/AI/llama.cpp/build/bin/llama-server` or `sh/navidc-ocr.sh`.
3. **Weight placement:** Always place new Hugging Face GGUF weights inside `models/<organization>/<repo-name>/`, and `audio.cpp` GGUFs in `models/audio-cpp/audio.cpp-gguf/`.
4. **Volume Hygeine:** This volume is mounted as NTFS3 (`/run/media/rodri/AI`). Do not store ephemeral Python virtualenvs (`.venv`), `node_modules`, or heavy build caches here. Keep `.venv` instances inside downstream harness folders on ext4 (`/home/rodri`).
5. **Token Efficiency:** When calling CLI skills from agents, use `--summary` or `--compact` flags where supported (e.g. `canvas-cli courses --summary`) to minimize token context consumption.
