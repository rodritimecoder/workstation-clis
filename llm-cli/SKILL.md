---
name: llm-cli
description: >
  Direct local CLI client for Qwen3.6-35B-A3B Uncensored Genesis on port :8080 (Dual RX 9060 XT
  Vulkan/ROCm offload, 131k context window). Supports direct code generation, system prompts,
  token streaming, response projection, disk buffering, health doctor, and cloud fallback.
---

# `llm-cli` — Workstation Flagship Model Client (`:8080`)

Direct client for the primary 22 GB Dual-GPU coding & reasoning model (`Qwen3.6-35B-A3B Uncensored Genesis`) on port `:8080`.

---

## 🛠️ Usage

```bash
# 1. Direct prompt
llm-cli "Write a python function to compute Levenshtein distance"

# 2. Stream tokens in real time
llm-cli --stream "Explain the difference between TCP and UDP"

# 3. Custom system prompt
llm-cli --system "You are a concise Linux kernel hacker." "How does eBPF work?"

# 4. Buffer output to disk (Uber Protocol)
llm-cli "Refactor this entire script: $(cat script.py)" --out /tmp/refactored.py

# 5. Check server readiness and VRAM status
llm-cli doctor

# 6. Launch server in background if offline
llm-cli start
```

---

## 🏛️ Local Inference Architecture
- **Port:** `http://127.0.0.1:8080/v1/chat/completions`
- **Model:** `Qwen3.6-35B-A3B Uncensored Genesis Final (Q4_0_ROCMFP4)`
- **VRAM Footprint:** 22 GB split across Dual Radeon RX 9060 XT (`-ts 45/55`)
- **Context Window:** 131,072 tokens
- **Launcher:** `/run/media/rodri/AI/sh/luffy_nothink.sh`
