---
name: audiocpp
description: Unified local audio intelligence hub wrapping audio.cpp v0.9.2 with Vulkan GPU acceleration on Dual AMD Radeon RX 9060 XT. Delivers sub-1.0 RTF (1.2x to 91.5x real-time) across 12 GGUF models: Nemotron-3.5-ASR (67x), CrisperWhisper 2.0 (8.5x verbatim ASR), Qwen3 Forced Aligner (91.5x), Supertonic-3 (38x TTS), Kokoro 82M (17x TTS), Kitten (12x TTS), Omnivoice (5x TTS), Audio8 (2.7x voice clone), Higgs 4B (2.5x TTS), Index-TTS 2.5 (1.4x voice clone), and Fish Audio S2 Pro (1.2x voice clone).
---

# `audiocpp` — Local Audio Intelligence Hub (`audio.cpp v0.9.2`)

Hardware-accelerated speech-to-text, text-to-speech, forced alignment, and voice cloning powered by `audio.cpp v0.9.2` on **Dual AMD Radeon RX 9060 XT** GPUs using Vulkan (`--backend vulkan --device 0`).

---

## ⚡ Verified Vulkan RTF Performance (100% Real-Time or Faster)

All 12 local GGUF models run faster than real-time (`RTF < 1.0`):

| Model | Family | Task | Audio (s) | Wall Time | RTF | Speed Multiplier | Key Specialty |
|---|---|---|---|---|---|---|---|
| **Aligner** | `qwen3_forced_aligner` | `align` | 5.48s | 59.9ms | **0.0109** | **91.5x** | Millisecond-accurate word boundaries |
| **Nemotron F16** | `nemotron_asr` | `asr` | 5.48s | 81.2ms | **0.0148** | **67.5x** | Ultra-fast streaming speech-to-text |
| **Nemotron Q8** | `nemotron_asr` | `asr` | 5.48s | 102.0ms | **0.0186** | **53.7x** | High-efficiency speech-to-text |
| **Supertonic-3** | `supertonic` | `tts` | 6.09s | 160.0ms | **0.0263** | **38.1x** | Instant conversational voice synthesis |
| **Kokoro 82M** | `kokoro_tts` | `tts` | 7.30s | 422.5ms | **0.0579** | **17.3x** | Expressive studio narration & voice IDs |
| **Kitten-TTS** | `kitten_tts` | `tts` | 9.94s | 818.9ms | **0.0824** | **12.1x** | Lightweight edge TTS |
| **CrisperWhisper 2.0** | `crisperwhisper` | `asr` | 5.48s | 641.5ms | **0.1171** | **8.5x** | Verbatim acoustic transcription & disfluencies |
| **Omnivoice** | `omnivoice` | `tts` | 5.52s | 1116.6ms | **0.2023** | **4.9x** | High-fidelity multi-speaker synthesis |
| **Audio8** | `audio8_tts` | `tts` | 5.62s | 2065.2ms | **0.3675** | **2.7x** | Zero-shot reference voice cloning |
| **Higgs Audio v3** | `higgs_audio_tts` | `tts` | 5.12s | 2053.6ms | **0.4011** | **2.5x** | 4B Flagship emotive voice generation |
| **Index-TTS 2.5** | `index_tts2` | `tts` | 6.30s | 4630.8ms | **0.7346** | **1.4x** | High-precision reference cloning |
| **Fish Audio S2 Pro** | `fish_audio` | `tts` | 5.67s | 4688.6ms | **0.8276** | **1.2x** | Production-grade zero-shot voice clone |

---

## 🛠️ Deterministic CLI Quickstart

The canonical executable is located at `~/.local/bin/audiocpp` (symlinked from `/run/media/rodri/AI/skills/audiocpp/scripts/audiocpp_cli.py`).

### 1. Speech-to-Text (`asr`) — Audio in $\rightarrow$ Text out
```bash
# Clean UNIX stdout: returns only transcript text for direct piping
audiocpp asr recording.wav > transcript.txt

# Ultra-fast transcription with Nemotron (67x real-time streaming)
audiocpp asr recording.wav --model nemotron

# High-precision verbatim ASR with CrisperWhisper 2.0
audiocpp asr speech.wav --model crisperwhisper

# Machine-readable typed JSON output (--json)
audiocpp asr speech.wav --json
# Output:
# {
#   "task": "asr",
#   "model": "crisperwhisper",
#   "text": "System diagnostic complete.",
#   "duration_s": 2.45,
#   "wall_ms": 78.4,
#   "rtf": 0.032,
#   "words": [...]
# }
```

### 2. Text-to-Speech (`tts`) — Text in $\rightarrow$ `.wav` Audio out
```bash
# Ultra-fast narration with Supertonic (38x real-time)
audiocpp tts "System diagnostic complete. All parameters nominal." --out notice.wav

# Studio narration with Kokoro voice ID (17x real-time)
audiocpp tts "Welcome back, Rodrigo." --model kokoro --voice af_bella --out welcome.wav

# Zero-shot voice cloning with Fish Audio or Audio8
audiocpp tts "Cloned voice sample." --model fish --voice-ref /run/media/rodri/AI/voice/maomao.wav --out clone.wav

# Machine-readable typed JSON output (--json)
audiocpp tts "Processing completed." --json
# Output:
# {
#   "task": "tts",
#   "status": "ok",
#   "audio_file": "/run/media/rodri/AI/output.wav",
#   "model": "supertonic",
#   "duration_s": 1.82,
#   "wall_ms": 94.2,
#   "rtf": 0.051
# }
```

### 3. Forced Alignment (`align`) — Word Timestamps
```bash
# Extract exact millisecond sample boundaries for animation / subtitles (91x real-time)
audiocpp align audio.wav "Exact transcript of the speech." --json
```

### 4. Hardware Health & Benchmarks
```bash
# Inspect Vulkan GPU device status and model availability
audiocpp doctor [--json]

# List all 12 installed models
audiocpp models [--json]

# Run the live RTF benchmark suite across all models
audiocpp benchmark [--json]
```


---

## 🏛️ Architecture & Paths

- **Canonical Repository**: `/run/media/rodri/AI/skills/audiocpp/`
- **Binary Directory**: `/run/media/rodri/AI/audio.cpp` -> `/run/media/rodri/AI/audio-v0.9.2-bin-ubuntu-x64-vulkan/`
- **Server Config**: `/run/media/rodri/AI/audio.cpp/server.json` (Port `8081`)
- **GGUF Weights Directory**: `/run/media/rodri/AI/models/audio-cpp/audio.cpp-gguf/`
- **Voice Clones Reference**: `/run/media/rodri/AI/voice/`
