---
name: video-miner

description: "Extract, transcribe, and synthesize knowledge from video files or URLs into structured markdown notes using local speech-to-text (Nemotron ASR), smart visual frame sampling with deduplication, text gating (vllm-d3-mini vision), and multi-column layout & code extraction (LightOnOCR-3-1B). Built on ICM (Interpretable Context Methodology) with staged folders and human review checkpoints."

compatibility: "Requires ffmpeg, the local Nemotron ASR server on :8081, the vllm-d3-mini decision model on :8083 for frame gating, and LightOnOCR on :8085 for layout extraction."
allowed-tools: "Bash(video-miner:*) Bash(ffmpeg:*) Bash(python3:*) Read Write"
---

# video-miner

Video mining pipeline combining local speech ASR and on-screen visual OCR into a unified, chronological markdown notes document.

Follows **Interpretable Context Methodology (ICM)**:
- Folders carry sequencing (`01_acquire` through `06_synthesize`).
- Files carry state: every stage has a `CONTEXT.md` contract and an `output/` edit surface.
- Human review checkpoints: inspect, edit, or adjust any stage before the next stage reads it.

## The 6 Stages

| Stage | Job | Input | Output & Human Checkpoint |
|---|---|---|---|
| `01_acquire` | Download/link video & extract 16 kHz audio | Video URL or path | `output/audio.wav`, `video_meta.json` |
| `02_audio_asr` | Transcribe speech via local `audiocpp-asr` (:8081 / CLI) | `01_acquire/output/audio.wav` | `output/transcript.md` *(edit/correct terms)* |
| `03_visual_sample` | Keyframe scene sampling, motion accumulator, mpdecimate & PTS timing | `01_acquire/output/source_video.mp4` | `output/frames/`, `manifest.json` |
| `04_visual_gate` | Filter frames for readable text / code | `03_visual_sample/output/manifest.json` | `output/gated_frames.json` *(check kept frames)* |
| `05_visual_ocr` | Multi-column layout, tree & code extraction via LightOnOCR-3-1B (Qwen3-VL on Vulkan) | `04_visual_gate/output/text_frames/` | `output/ocr_timeline.md` *(fix OCR typos)* |
| `06_synthesize` | Merge audio transcript & visual OCR into notes | `02_audio_asr` + `05_visual_ocr` | `output/mined_video.md` *(final deliverable)* |


## Quick Usage

### 1. Initialize a video mining workspace

```bash
CLI=~/.gemini/config/skills/video-miner/scripts/videomine.py
python3 $CLI init ./my_video_run "https://www.youtube.com/watch?v=..."
# Or with a local video file:
python3 $CLI init ./lecture_run ~/Videos/lecture.mp4
```

### 2. Check pipeline status (ASCII diagram or Token-Shielded table)

```bash
# Default ASCII flowchart:
python3 $CLI status ./my_video_run

# Token-shielded Markdown pipe table with artifacts:
python3 $CLI status ./my_video_run --table
```

### 3. Timeline Outline & Chapter Bookmarks (Glitch Cat / Kem Architecture)

Instead of reading 30k tokens of full synthesized video notes, extract a high-density chronological timeline table (~150 tokens):

```bash
# High-density timeline of visual slides and speech checkpoints:
python3 $CLI outline ./my_video_run --table

# Project specific columns and cap rows:
python3 $CLI outline ./my_video_run -p time,type,preview -n 15

# Buffer full timeline JSON to disk with receipt:
python3 $CLI outline ./my_video_run -o ./checkpoints.json
```

### 4. Step through one stage at a time (Human Checkpoint Mode)

Run the next stage and stop so you can review and edit intermediate files:
```bash
python3 $CLI step ./my_video_run
```

### 5. Run up to a specific checkpoint

```bash
# E.g. run acquisition and ASR first, then pause for transcript review:
python3 $CLI run ./my_video_run --until 02_audio_asr
```

### 6. Run the entire pipeline end-to-end

```bash
python3 $CLI run ./my_video_run
```

The final synthesized markdown document is emitted at:
`./my_video_run/stages/06_synthesize/output/mined_video.md`

## Human Checkpoints & Editing

Because every stage output is an edit surface:
- **Audio Transcript Checkpoint (`02_audio_asr`):** Open `stages/02_audio_asr/output/transcript.md` and correct any misrecognized technical jargon or names. Downstream synthesis will use your edits.
- **Visual Gating Checkpoint (`04_visual_gate`):** Inspect `stages/04_visual_gate/output/gated_frames.json`. If a slide or code frame was excluded, toggle `"keep": true`.
- **OCR Checkpoint (`05_visual_ocr`):** Open `stages/05_visual_ocr/output/ocr_timeline.md` and polish any code blocks before final merge.

---

## 🏛️ Creator Video Vault (`vault-mine`)

High-speed single-pass video mining and cataloging into `/run/media/rodri/AI/creator-vault/`. Powered by `audiocpp` GPU speech-to-text (8.5x–67x real-time), single-pass download with info JSON, and smart OCR gating:

```bash
# List vaulted videos in a high-density Markdown table:
vault-mine list --table --limit 10

# Filter vault by creator:
vault-mine list --creator "kem_glitch" --table

# Fast single-pass video mining directly from URL into the vault (~12s end-to-end):
vault-mine add "https://www.instagram.com/reel/..." --creator "kem_glitch" --title "graph-memory-rant"

# Ultra-fast mining with Nemotron streaming STT:
vault-mine add "https://..." --model nemotron

# Import an existing mined ICM workspace into the vault:
vault-mine import ./my_video_run --creator "kem_glitch" --title "5-agents-worktree"

# Rebuild vault catalog index:
vault-mine reindex
```

## Tests

```bash
python3 ~/.gemini/config/skills/video-miner/scripts/test_videomine.py
```

