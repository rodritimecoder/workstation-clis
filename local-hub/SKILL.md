---
name: local-hub
description: Unified local workstation inference hub and CLI gateway for Dual-GPU AMD Radeon hardware: Genesis 35B coder (:8080), LightOnOCR-3-1B vision (:8085), Imajev-4B calibrated decisions (:8083), Nemotron 3.5 ASR (:8081), live health checks, and skill discovery.
---

# `local-hub` — Workstation Inference & Skills Gateway

Unified CLI and skill hub providing direct access to all local GPU inference models running on dual AMD Radeon RX 9060 XT GPUs (32GB VRAM), plus the Uber OmniMCP late-binding discovery protocol.

---

## ⚡ Native Local Engine Commands

### 1. `local-hub llm` — Dual-GPU Flagship Coder (:8080)
Direct client for **Qwen3.6-35B-A3B Uncensored Genesis** (22 GB ROCMFP4, dual-GPU offload `-ts 45/55`, 131k context window).

```bash
# Direct generation
local-hub llm "Write a Python script to monitor GPU thermals"

# Stream response tokens
local-hub llm "Explain raft consensus" --stream

# Buffer output to file
local-hub llm "Generate database schema" --out schema.sql

# Fallback to cloud if :8080 is offline
local-hub llm "Complex query" --fallback

# Health check & model launcher
local-hub llm doctor
local-hub llm start
```

---

### 2. `local-hub ocr` — Flagship Document & Slide OCR (:8085)
Direct local OCR client for **LightOnOCR-3-1B** (~16,000 tokens/sec prefill, ~330 tokens/sec generation) and CrispEmbed scene text.

```bash
# OCR a slide, diagram, or photo
local-hub ocr slide_frame.png

# OCR specific pages of a PDF to markdown
local-hub ocr lecture.pdf --pages 1-5 -o lecture_notes.md

# Format ASCII directory trees / listings into clean Markdown lists
local-hub ocr terminal_screenshot.png --tree

# Check engine health and model files
local-hub ocr --doctor
```

---

### 3. `local-hub decide` (or `local-hub jev`) — Calibrated Decision Gating (:8083)
Queries **Imajev-4B** ($T=1.305$) and **JPT-4B** (:8090) for calibrated probabilities, classification, scoring, and binary gating.

```bash
# 1. Binary Decision (noul) -> P(true)
local-hub decide "User wants a refund after 60 days." "Is this within 30-day policy?"
# Output: {"model": "imajev", "type": "noul", "answer": false, "p_true": 0.02, "confidence": 0.98}

# 2. Multi-class Choice -> argmax + probability distribution
local-hub decide "Crash log showing null pointer" "Which component failed?" '{"db": "database", "ui": "frontend", "net": "network"}'

# 3. Ordered Score -> expected level
local-hub decide "Customer review text" "Rate sentiment" '["negative", "neutral", "positive"]'

# Cross-check multiple models
local-hub decide "State text" "Question" --cross-check imajev,jpt
```

---

### 4. `local-hub asr` — Streaming Speech-to-Text (:8081)
Transcribe audio files or run live microphone dictation using the `audio.cpp` server with **Nemotron 3.5 ASR** (40 languages, word timestamps).

```bash
# Transcribe audio file to text
local-hub asr transcribe meeting.mp3

# Output with word-level timestamps to markdown
local-hub asr transcribe lecture.m4a --format md -o transcript.md

# Live microphone dictation
local-hub asr live

# Health check
local-hub asr doctor
```

---

### 5. `local-hub status` (or `local-hub health`) — Port Health Table
Live ping of all local hardware inference endpoints (:8080–:8090) and Tailscale mesh status:

```bash
local-hub status
local-hub status --json
```

---

## 🔍 Skill Discovery & Gateway Protocol

In addition to local inference, `local-hub` provides late-binding discovery across all workstation skills:

```bash
# Search skills by intent
local-hub search "git worktree parallel"

# List scripts inside a skill
local-hub tools worktree-harness

# Read usage rubric for 1 skill
local-hub inspect worktree-harness

# Execute any skill with disk buffering and response projection
local-hub run openrouter-free "prompt" --out /tmp/out.txt --project "content"
```
