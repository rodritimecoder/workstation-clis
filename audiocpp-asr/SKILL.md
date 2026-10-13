---
name: audiocpp-asr
description: "Local speech-to-text using the audio.cpp server's Nemotron 3.5 ASR model: transcribe audio files (wav/mp3/m4a/flac/ogg/opus) with 40-language support, word-level timestamps, hotword prompting, and live microphone dictation. Use whenever asked to transcribe, dictate, or get a text transcript of an audio or video file, meeting recording, lecture, or voice note."
metadata:
  author: pi-user
  version: "1.0"
---

# audiocpp-asr

Speech-to-text from the [audio.cpp](https://github.com/0xShug0/audio.cpp) server
(Nemotron 3.5 ASR, a 0.6B RNNT model). Everything runs locally on the GPU.

## Start the server first

Double-click **`~/Desktop/audio.cpp-server.desktop`**, or run:

```bash
/run/media/rodri/AI/audio-v0.9.0-bin-ubuntu-x64-vulkan/run-audiocpp.sh     # GPU, :8081
~/audio-v0.9.0-cpu/run-audiocpp.sh         # CPU-only, :8082
```

**audio.cpp 0.9.0** (`git 795c45fb`, 2026-09-30). Install dirs are `~/audio-v0.9.0-<backend>/`
— `audiocpp_cli`, `server.json` and `model_specs/` all live together there. The old
`~/Desktop/audio-v0.8.2-…` tree is gone; any path pointing at it is broken.

It serves TTS and ASR (`nemotron-asr`) on `127.0.0.1:8081`.
The skill never starts or stops it. Check with:

```bash
python3 ~/.gemini/config/skills/audiocpp-asr/scripts/asr.py doctor
```

**`--engine cli` needs no server at all** — see below.

## Usage

```bash
ASR=~/.gemini/config/skills/audiocpp-asr/scripts/asr.py
python3 $ASR <command> [options]
```

### Transcribe files

```bash
python3 $ASR transcribe lecture.mp3
python3 $ASR transcribe a.wav b.m4a -o transcripts.txt      # several files
python3 $ASR transcribe meeting.m4a --language es-ES
python3 $ASR transcribe talk.wav --prompt "Kanban, Kubernetes, PostgreSQL"
python3 $ASR transcribe talk.wav --details                   # word timestamps (JSON)
python3 $ASR transcribe talk.wav --stream                    # SSE deltas while decoding
```

Any audio format is accepted; anything that isn't already 16 kHz mono is
normalised first with GStreamer. This is required, not optional: the server only
decodes MP3/FLAC natively if it was built with the `audio_decode` frontend
module, and **the default server build has no frontend modules**.

### Live dictation

```bash
python3 $ASR live
```

Streams the microphone to the server and prints partial text as you speak.
Ctrl-C to stop; `-o out.txt` saves the final transcript. Capture is 16 kHz mono
s16 PCM in **320 ms chunks** — the cadence `nemotron_asr` is tuned for.

### Offline mode (no server, better for whole files)

```bash
python3 $ASR transcribe long-lecture.wav --engine cli
```

Shells out to `audiocpp_cli` with `--mode offline` against the same GGUF. Use this
for files where full-context accuracy beats latency. See *Modes* below.

## Modes: why your server is set to `streaming`

`server.json` configures `nemotron-asr` with `"mode": "streaming"`. **That is
correct and you should leave it** — `mode` is model *configuration*, fixed at
load time, and two features require streaming mode:

- `asr.py live` (the live route only accepts a model configured `mode: "streaming"`)
- `transcribe --stream` (SSE deltas)

The cost is that file transcription also runs as a streaming session rather than
full-context offline. `mode` **cannot be changed per request** — verified three
ways:

1. The documented request fields are `model`, `audio`/`file`, `language`,
   `prompt`, `options`, and `busy_timeout_ms`. There is no `mode`.
2. The WebUI's own ASR call sends `{model, audio, language, options}` — no mode.
3. `POST /v1/models/load` (which *would* take a `mode`) returns
   `403 dynamic model management is disabled` under your config.

So for whole-file accuracy use `--engine cli`, which defaults to
`--mode offline` and needs no server. Adding a second offline model to
`server.json` is the other option, but `max_loaded_models: 2` is already met by
TTS + ASR, so a third id would cause LRU reload churn (or 503s under load).

## Request options

`--option key=value` (repeatable) builds the request's `options` object — the same
field the WebUI uses. Values are typed, so `13` arrives as a number and `true` as
a boolean.

```bash
python3 $ASR transcribe talk.wav \
  --option lookahead_tokens=13 \
  --option keep_language_tags=true \
  --option max_tokens=0
```

Documented `nemotron_asr` options:

| Option | Meaning |
|---|---|
| `lookahead_tokens` | chunk-limited encoder right context |
| `keep_language_tags` | keep language tag tokens in the decoded text |
| `max_tokens` | cap on generated tokens; `0` = model limit |
| `speaker_probabilities` | path to a `nemotron_3_diar` output for speaker-tagged transcription |
| `speaker_mode` | `masked` (default) or `attribution` |
| `speaker_mask` | `mel` (default) or `audio` |
| `speaker_segment_gap_sec` | pause before a new speaker segment (default 1.0) |
| `speaker_segment_max_sec` | split speaker turns after this long (streaming, default 10.0) |

Speaker tagging needs a diarization model, which is **not downloaded yet**.

## Languages

40 locales. `python3 $ASR languages` lists them. Pass `--language es-ES`, or
`--language auto` to detect.

## Timestamps

`--details` returns word/segment spans. The model reports **sample offsets, not
seconds** — `start_sample` / `end_sample`, with `sample_rate` alongside. The skill
adds `start_sec` / `end_sec` so you don't have to divide by hand.

`--details` and `--stream` are mutually exclusive: the SSE response carries
deltas only and has nowhere to put the timestamp arrays.

## Other commands

```bash
python3 $ASR doctor        # server, loaded models, weights, audio tooling
python3 $ASR languages     # the 40 supported locales
```

## Configuration

Set in `.env` beside the script, or export:

| Variable | Default |
|---|---|
| `AUDIOCPP_BASE` | `http://127.0.0.1:8081` |
| `AUDIOCPP_ASR_MODEL` | `nemotron-asr` |
| `AUDIOCPP_ASR_MODEL_PATH` | the f16 GGUF in the audio.cpp model dir |
| `AUDIOCPP_ASR_LANGUAGE` | `en-US` |
| `AUDIOCPP_CLI` | `/run/media/rodri/AI/audio-v0.9.0-bin-ubuntu-x64-vulkan/audiocpp_cli` (auto-detected) |
| `AUDIOCPP_APP_DIR` | the audio.cpp install dir |

## Notes

- One model serves one request at a time; a second queues, then 503s after
  `busy_timeout_ms` (300 s in your config).
- The first request per model pays the lazy-load cost.
- The live route requires a terminating chunk; closing the socket without one is
  an error by design, not end-of-speech.
- Multi-file runs issue one request per file. The server has a native
  `/v1/batches/transcriptions` route, but it only accepts models with native
  batching support.
- This is ASR only. TTS lives in the same server but is out of scope here.

## Tests

```bash
python3 ~/.gemini/config/skills/audiocpp-asr/scripts/test_asr.py
```

22 offline tests against a stub server, including the chunked live-socket
protocol and GStreamer normalisation.

## Choosing a different model

The server loads several ASR models side by side; this skill is not tied to Nemotron. Weights live
in `$AUDIOCPP_GGUF_DIR` (default `/run/media/rodri/AI/models/audio-cpp/audio.cpp-gguf`).

```bash
export AUDIOCPP_ASR_MODEL=qwen3-asr      # server model id  (or --model)
export AUDIOCPP_ASR_FAMILY=qwen3_asr    # family for --engine cli  (or --family)
export AUDIOCPP_ASR_MODEL_PATH=.../qwen3-asr-0.6b-q8_0.gguf
python3 scripts/asr.py doctor           # confirms the server actually loaded it
```

`doctor` prints every loaded model and flags if your `--model` is absent — then the server needs a
restart to pick up a newly dropped GGUF.

**Read `references/asr-model-options.md` before adding one.** Short version: Whisper is not in
audio.cpp, and the fix for fragmentary RNNT word tokens is `qwen3_forced_aligner`, not a bigger
recogniser — you already have clean text from captions, so align known text instead of re-hearing it.

Weights dir is on `/dev/nvme0n1p6`, 21G used of 250G. Check headroom before pulling another 1-2G model.
