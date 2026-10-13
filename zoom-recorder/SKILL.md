---
name: zoom-recorder
description: "Download transcripts, audio, and visual keyframe slides from Zoom cloud recordings (utsmeet.zoom.us and *.zoom.us) without requiring Zoom API admin credentials. Supports password validation, unwrapping Outlook/Mimecast protection URLs, and automated scraping/extraction from Canvas LMS pages and modules."
---

# Zoom Recorder & Transcript Skill

A high-efficiency skill for downloading Zoom cloud recordings (`/rec/play/...` and `/rec/share/...`) focused on **transcripts (VTT / Markdown)** and **presentation keyframes** without wasting bandwidth downloading 1-hour heavy video files.

## Features

1. **Native Passcode Support Without Admin API Credentials**:
   - Zoom cloud recordings hosted on institutional domains (`utsmeet.zoom.us`, `*.zoom.us`) protected with passcodes are authenticated directly via Zoom's web playback validation flow.
2. **Transcript-First Extraction**:
   - Fetches native Zoom `.vtt` closed-caption and speaker transcripts in milliseconds.
   - Automatically formats transcripts into human-readable Markdown with timestamps and speaker tags (`- [00:03:20] **Trong Toan Tran**: ...`).
3. **Smart URL Protection Unwrapping**:
   - Automatically unrolls university protection wrappers like **Mimecast** (`mimecastprotect.com`) and **Microsoft SafeLinks** (`protection.outlook.com`).
4. **Selective Keyframe Extraction & Local Vision OCR**:
   - Streams presentation video via authenticated HTTP session directly into `ffmpeg pipe:0` with scene-change detection (`select='gt(scene,0.35)'`), grabbing slide transitions without downloading the 1-hour video file.
   - Built-in multi-model OCR benchmarking directly on extracted slides via local GGUF models:
     - `lighton` (**LightOnOCR-3-1B**): Blazing fast (<1s), clean Markdown layout, accurate LaTeX mathematical equations.
     - `xiaomi` (**Xiaomi-OCR-0**): Reasoning OCR, LaTeX formulas, clean formatting.
     - `deskforge` (**DeskForge-Qwen3.5-4B**): Complete document & Markdown hierarchy preservation with units formatted (`\mu\text{F}`).
     - `ovis` (**OvisOCR2-5B**): High-detail UI & on-screen text extraction.
5. **Canvas LMS Integration**:
   - Connects directly with `canvas-cli` to scan course modules/pages, automatically extract Zoom recording URLs and passcodes, and download transcripts into the course's notes directory.

---

## Quick Start (Standalone Usage)

Run the script located in `scripts/zoom_download.py`:

```bash
# 1. Download Markdown transcript of a passcode-protected Zoom recording:
python3 ~/.gemini/config/skills/zoom-recorder/scripts/zoom_download.py \
  --url "https://utsmeet.zoom.us/rec/share/5B7QIAjUKfS54PORwr1ijvJPEor3z5loikK0quVCTfkfZ_OQwAeMAY3KAT6_A9dv.CJTU0_s9zKosU0oP" \
  --passcode "S!6o2WH?" \
  --out-dir "./transcripts" \
  --format md

# 2. Extract slide keyframes & run local Vision OCR (e.g. LightOnOCR):
python3 ~/.gemini/config/skills/zoom-recorder/scripts/zoom_download.py \
  --url "https://utsmeet.zoom.us/rec/share/Zlc_xsAjWO858kllE6q-MUHpmMopUt95p4UNSrfshTk2JamQ-KewJwkCQjvZNR_8.G7qIJtGRiOSdcCZ3" \
  --passcode "#5yN5N^6" \
  --ocr \
  --ocr-model lighton \
  --out-dir "./week10_slides"

# 3. Benchmark ALL local vision OCR models on the slides:
python3 ~/.gemini/config/skills/zoom-recorder/scripts/zoom_download.py \
  --url "https://utsmeet.zoom.us/rec/share/..." \
  --passcode "Secret123" \
  --ocr \
  --ocr-model all \
  --out-dir "./benchmark"
```

### CLI Arguments

| Argument | Description | Default |
|---|---|---|
| `--url <url>` | Zoom cloud recording URL (`/rec/play` or `/rec/share`) | Required |
| `--passcode, -p <pwd>` | Recording passcode (if protected) | `""` |
| `--out-dir, -o <dir>` | Destination folder for saved files | `.` |
| `--format` | Output format: `md` (Markdown), `vtt` (raw WebVTT), `txt` (plain text), `all` | `md` |
| `--keyframes` | Stream video with ffmpeg to extract slide changes | Disabled |
| `--scene-threshold` | Sensitivity for slide change scene detection (`0.0` - `1.0`) | `0.35` |
| `--json` | Print extracted recording metadata to stdout as JSON | Disabled |

---

## Integration with `canvas-cli`

When university lecture/tutorial recordings are posted as Canvas pages or announcements with passcodes, use the automated pipeline in `examples/canvas_zoom_pipeline.py`.

### Workflow Example

```bash
# Scan Canvas Course 41088 (Electronics and Circuits), find all tutorial Zoom recordings & passcodes,
# and automatically save their transcripts into the subject's notes folder:
python3 ~/.gemini/config/skills/zoom-recorder/examples/canvas_zoom_pipeline.py \
  --course-id 41088 \
  --out-dir ~/Downloads/notes/48520\ -\ Electronics\ and\ Circuits/recordings \
  --format md
```

### How the Pipeline Works:
1. Calls `canvas-cli modules <course_id>` to list all weekly modules.
2. Fetches page items inside each module (e.g. `Week 1 - Tutorial video recording - Passcode: S!6o2WH?`).
3. Uses regular expressions to parse out the Zoom replay URL and the `Passcode: <password>`.
4. Passes each recording to `zoom_download.py` which un-protects the Mimecast link, authenticates with Zoom, and writes clean Markdown transcripts grouped by week.

---

## Downstream Study Workflow (With `cornell-notes`)

Once transcripts are downloaded as Markdown, you can feed them directly into the `cornell-notes` skill:

```bash
# Generate Cornell Notes HTML revision sheets from the Zoom lecture transcript:
python3 ~/.gemini/config/skills/cornell-notes/scripts/cornell_notes.py \
  --input ~/Downloads/notes/zoom_transcripts/Week_1/tutorial_transcript.md \
  --output ~/Downloads/notes/zoom_transcripts/Week_1/tutorial_cornell.html
```
