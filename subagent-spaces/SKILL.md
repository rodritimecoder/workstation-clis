---
name: subagent-spaces
description: "Isolated CPU-pinned containerized sandbox environments for autonomous subagents using rootless Podman. Partitions 16 CPU threads into dedicated worker slots, mounts disposable workspaces, isolates untrusted builds and scripts, and connects directly to local inference endpoints."
---

# Subagent Spaces (`subagent-spaces`)

Isolated, CPU-pinned containerized sandbox environments for autonomous subagents running locally via rootless Podman.

Instead of running builds, tests, or untrusted code directly on the host or incurring cloud VM latency, `subagent-spaces` partitions your CPU threads into dedicated worker slots with strict memory quotas, disposable workspace mounts, and zero blast-radius.

---

## 🖥️ CPU Core Topology (16-Thread Ryzen Substrate)

| Slot | CPU Threads | RAM Quota | Purpose |
|---|---|---|---|
| **`HOST`** | `0–3` (4 threads) | Unlimited | Reserved for Host OS, Desktop, Display Server, & GPU drivers |
| **`Slot 1`** | `4–7` (4 threads) | `4 GB` | Dedicated worker space for Subagent 1 |
| **`Slot 2`** | `8–11` (4 threads) | `4 GB` | Dedicated worker space for Subagent 2 |
| **`Slot 3`** | `12–15` (4 threads) | `4 GB` | Dedicated worker space for Subagent 3 |
| **`all`** | `4–15` (12 threads) | `12 GB` | Full-throttle single-task compilation / heavy batch run |

---

## 🚀 Quick Usage

### 1. Check System Health & Doctor
Verifies Podman, cgroups, `taskset` CPU core pinning, and local images:
```bash
subagent-spaces doctor
```

### 2. View Active Slot Occupancy
Displays an ASCII topology table showing which worker slots are IDLE or OCCUPIED:
```bash
subagent-spaces slots
```

### 3. Run a Command in an Isolated Space
Runs a command inside a pinned container. Automatically selects the first idle slot:
```bash
# Auto-assign slot and run tests in current directory
subagent-spaces run -- pytest

# Explicit slot, specific workspace, and read-only mount
subagent-spaces run --slot 1 --workspace ~/projects/app --ro -- python3 test.py

# Detached background subagent
subagent-spaces run --slot 2 -d --name worker-task -- npm run build
```

### 4. Interactive Shell into a Space
```bash
# Attach interactive bash to Slot 2 or container name
subagent-spaces enter 2
```

### 5. Inspect Running Spaces
```bash
subagent-spaces ps
```

### 6. Stop or Prune Spaces
```bash
# Stop a specific space
subagent-spaces stop 2

# Clean up all active spaces
subagent-spaces prune
```

### 7. Build Local Development Image
Builds `subagent-space:latest` with Python 3, Git, curl, jq, and build tools:
```bash
subagent-spaces build
```

---

## 🌐 Local Inference Connectivity
By default, spaces use `--network host`, enabling sandboxed subagents to seamlessly query your workstation's local LLM and speech servers:
* `http://127.0.0.1:8080` — Primary LLM (Qwen 35B)
* `http://127.0.0.1:8081` — Nemotron 3.5 ASR (`audiocpp-asr`)
* `http://127.0.0.1:8083` — Imajev-4B Decision (`jev-cli`)
* `http://127.0.0.1:8085` — LightOnOCR-3-1B (`ocr-cli`)
