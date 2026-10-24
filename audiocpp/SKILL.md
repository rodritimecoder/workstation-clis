---
name: audiocpp

description: >
  Local audio intelligence: speech-to-text, text-to-speech, forced alignment and
  voice cloning across 12 GGUF models, every one of them faster than real time
  on dual RX 9060 XT GPUs. Use for transcription, narration, cloning, or
  millisecond word timestamps.

compatibility: "Requires Dual AMD Radeon RX 9060 XT GPUs with Vulkan and the audio.cpp v0.9.0 binary."
allowed-tools: "Bash(audiocpp:*) Bash(python3:*) Read Write"
---

# Local Audio Intelligence (`audiocpp`)

Hardware-accelerated speech-to-text, text-to-speech, forced alignment and voice
cloning, powered by `audio.cpp v0.9.2` on **dual AMD Radeon RX 9060 XT** GPUs
over Vulkan. Every model runs faster than real time, so a minute of audio
transcribes in under a second and a sentence narrates in under fifty
milliseconds.

---

## 🏛️ The Models

| Model | Task | Reach for it when |
| :--- | :--- | :--- |
| `nemotron` | `asr` | Fast streaming transcription — the default |
| `crisperwhisper` | `asr` | Verbatim accuracy, keeping disfluencies |
| `supertonic` | `tts` | Instant conversational speech — the default |
| `kokoro` | `tts` | Expressive narration, or a named voice ID |
| `fish_audio` | `tts` | Zero-shot voice cloning from a reference clip |
| `qwen3_forced_aligner` | `align` | Millisecond word boundaries for subtitles |

---

## 🛠️ CLI Quickstart

```bash
AC="/run/media/rodri/AI/skills/audiocpp/scripts/audiocpp_cli.py"

# 1. Transcribe — clean stdout, pipes straight into a file
python3 $AC asr recording.wav > transcript.txt

# 2. Transcribe with a specific model
python3 $AC asr recording.wav --model nemotron
python3 $AC asr speech.wav --model crisperwhisper

# 3. Transcribe to typed JSON
python3 $AC asr speech.wav --json
# {
#   "task": "asr",
#   "model": "crisperwhisper",
#   "text": "System diagnostic complete.",
#   "duration_s": 2.45,
#   "wall_ms": 78.4,
#   "rtf": 0.032,
#   "words": [...]
# }

# 4. Narrate to a wav file
python3 $AC tts "System diagnostic complete. All parameters nominal." --out notice.wav

# 5. Narrate with a named voice
python3 $AC tts "Welcome back, Rodrigo." --model kokoro --voice af_bella --out welcome.wav

# 6. Clone a voice from a reference clip
python3 $AC tts "Cloned voice sample." --model fish --voice-ref /run/media/rodri/AI/voice/maomao.wav --out clone.wav

# 7. Synthesize to typed JSON
python3 $AC tts "Processing completed." --json

# 8. Extract word-level timestamps
python3 $AC align audio.wav "Exact transcript of the speech." --json

# 9. Inspect the binary, the Vulkan device, and the installed models
python3 $AC doctor [--json]

# 10. List all 12 installed models
python3 $AC models [--json]

# 11. Run the live RTF benchmark across every model
python3 $AC benchmark [--json]

# 12. Talk to a remote node over Tailscale
export AUDIOCPP_HOST="rodri-x870-taichi-creator.tail2975a8.ts.net"
python3 $AC doctor --host "$AUDIOCPP_HOST"
python3 $AC asr speech.wav --model crisperwhisper
python3 $AC tts "Synthesizing from laptop over Tailscale" --model kokoro -o speech.wav
```

---

## Reference

- `references/benchmarks.md` — measured RTF, wall time and speed for all 12 models
- `references/architecture.md` — canonical paths, binary directory, server config, weights
