---
name: pi-emote-icm
description: Autonomous ICM pipeline for generating, pixelating, and assembling custom 10-state pixel art avatar sets for pi-emote (https://github.com/cgxeiji/pi-emote). Takes 1 raw concept image, removes background, squares to 1:1, snaps to a 32x32 retro grid, scales via Nearest-Neighbor to 128x128, decomposes modular layers (eyes, 4 talk mouth weights, props), and compiles production-ready emote sets with validated emotes.json.
---

# `pi-emote-icm` — Pixel Art Avatar Pipeline for `pi-emote`

Transforms a single raw avatar concept into a character-consistent, 10-state animated emote set with 4 talk variations for [pi-emote](https://github.com/cgxeiji/pi-emote).

---

## 🏛️ The 6-Stage ICM Pipeline

```text
pi-emote-workspaces/<avatar-slug>/
├── 01_concept/          # Raw AI image or sketch (Gemini / Qwen-Image / hand-drawn)
├── 02_squared_nobg/     # Chroma-keyed alpha channel & 1:1 square canvas (128x128)
├── 03_pixelated/        # 32x32 quantized pixel master + 128x128 Nearest-Neighbor master
├── 04_layers/           # Modular sprite slices (base body, eyes open/blink/think/x, 4 mouth weights, props)
├── 05_states/           # Composited frames for all 10 states
│   ├── idle/ (idle.png, idle_blink.png)
│   ├── think/ (think.png, think_hard.png)
│   ├── talk/ (talk_close, talk_small, talk_mid, talk_wide)
│   ├── read/, write/, tool/, hi/, success/, failure/, compact/
└── 06_dist/             # Production package ready for ~/.pi/agent/extensions/pi-emote/emotes/<slug>/
    ├── emotes.json      # Frame weights and blink configuration
    └── ...              # All 128x128 PNGs
```

---

## ⚡ CLI Quickstart

### 1. Authentic Sprite Sheet Slicing (Recommended for Expressive Characters)
When prompting image generation models (Gemini, Qwen-Image, etc.), request a **2x2 sprite sheet on a solid green (`#00FF00`) background**:
- **Top-left**: Neutral / Idle (mouth closed, eyes open)
- **Top-right**: Blink (eyes closed softly, mouth closed)
- **Bottom-left**: Talk small (slightly open mouth, eyes open)
- **Bottom-right**: Talk wide (expressive open talking mouth, eyes open)

Then slice, defringe, assemble all 10 states, generate a showcase GIF, and install in one shot:
```bash
pi-emote-icm slice-sheet sprite_sheet.png --slug purple_girl --grid 2x2 --install --gif
```

### 2. All-in-One Build & Install (Single Image)
```bash
# Process raw concept into full pi-emote set and install directly into pi-emote:
pi-emote-icm build avatar_concept.png --slug cyberpunk_cat --grid 32 --install
```

### 3. Step-by-Step ICM Workflow
```bash
# Step 1: Scaffold workspace
pi-emote-icm init cyberpunk_cat --dir ./workspaces

# Step 2: Pixelate & snap to 32x32 grid with Nearest-Neighbor upscale
pi-emote-icm pixelate concept.png --grid 32 --out pixel_128.png

# Step 3: Decompose into modular sprite layers
pi-emote-icm decompose pixel_128.png --out-dir ./layers

# Step 4: Assemble all 10 states and emotes.json
pi-emote-icm assemble ./layers --states-dir ./states --dist-dir ./dist

# Step 5: Install into active pi-emote configuration
pi-emote-icm install ./dist cyberpunk_cat --target user
```

---

## 🎯 State & Variation Specifications

| State | Files | Trigger in `pi-emote` |
|---|---|---|
| **`idle`** | `idle.png`, `idle_blink.png` | Inactive / listening |
| **`think`** | `think.png`, `think_hard.png` | Reasoning tokens streaming |
| **`talk`** | `talk_close.png` (0.15)<br/>`talk_small.png` (0.30)<br/>`talk_mid.png` (0.35)<br/>`talk_wide.png` (0.20) | Text response streaming |
| **`read`** | `read.png` | `read` tool executing |
| **`write`** | `write.png` | `write` / `edit` tool |
| **`tool`** | `tool.png` | Any other bash or CLI tool |
| **`hi`** | `hi.png` | Session start greeting |
| **`success`** | `success.png` | Tool succeeded |
| **`failure`** | `failure.png` | Tool error / failure |
| **`compact`** | `compact.png` | Context compaction event |
