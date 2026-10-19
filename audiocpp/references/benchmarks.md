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
