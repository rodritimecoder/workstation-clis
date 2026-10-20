# AI Inference & Models Volume (`/run/media/rodri/AI`)

Authoritative catalog of local AI inference engines, model weights, port bindings, and agent skills on this machine.

**Host Hardware:** Dual AMD Radeon RX 9060 XT GPUs (Navi 44, Vulkan + ROCm).

---

## Active Ports & Inference Services

Always check health before launching (`curl -s http://127.0.0.1:<port>/health`).

| Port | Service | Default Model | Launcher | Health Check | Owning skill |
|---|---|---|---|---|---|
| `:8080` | `llama-server` (Vulkan) | `Qwen3.6-35B-A3B Uncensored Genesis` | `sh/luffy_nothink.sh` | `curl -s http://127.0.0.1:8080/health` | `local-llm` |
| `:8081` | `audio.cpp` (Vulkan) | `nemotron-asr`, `kokoro-v1.0`, `qwen3-forced-aligner` | `audio-v0.9.0-bin-ubuntu-x64-vulkan/run-audiocpp.sh` | `curl -s http://127.0.0.1:8081/health` | `audiocpp` |
| `:8083` | `llama-server` b11729+ (Vulkan) | `vllm-d3-mini-Q4_K_M` + `mmproj` (vision) | `sh/vllm-d3-mini.sh` | `curl -s http://127.0.0.1:8083/health` | `jev-decision` |
| `:8084` | `crispembed-server` | `CrispEmbed Scene Text (DBNet + PARSeq)` | `sh/crispembed-ocr.sh` | `curl -s http://127.0.0.1:8084/health` | `ocr --model crispembed` |
| `:8085` | `llama-server` (Vulkan) | `LightOnOCR-3-1B` | `sh/lighton-ocr.sh` | `curl -s http://127.0.0.1:8085/health` | `ocr` |

---

## Local Inference Skills

Each service is reached through the skill that owns it. There is no gateway
process in between: the agent reads the skill's `SKILL.md` and runs its
bundled script directly.

| Service | Skill | Invocation |
|---|---|---|
| LLM coder (:8080) | `local-llm` | `python3 hardware/local-llm/scripts/llm_client.py "<prompt>"` |
| Speech-to-text (:8081) | `audiocpp` | `audiocpp asr transcribe <audio> --out <file>` |
| Calibrated decisions + vision gating (:8083) | `jev-decision` | `jev bool|choice|score ...` |
| Vision document & slide OCR (:8085 / :8084) | `ocr` | `ocr <file> --pages 1-3 -o <file>` |

All four support `--out` so a large result lands on disk instead of in the
context window; the JSON-emitting ones also accept `--json` and field
projection.

---

## Skill Discovery

Discovery is the harness's job, not a router's. Every harness loads each
skill's `name` and `description` at startup (the Agent Skills spec calls this
the *discovery* step), the agent activates the one that matches, and reads
that skill's `SKILL.md`. `skills-ref to-prompt` renders the same
`<available_skills>` block for any tool that wants it.

Do not dump static skill lists into prompts, and do not hardcode paths: a
`SKILL.md` refers to its own files relatively (`scripts/…`, `references/…`)
and the agent resolves them from the skill root.

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
