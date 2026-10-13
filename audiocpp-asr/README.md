# audiocpp-asr

Local speech-to-text skill wrapping the ASR half of
[audio.cpp](https://github.com/0xShug0/audio.cpp) — Nemotron 3.5 ASR (0.6B RNNT)
on the GPU. File transcription with word timestamps, and live microphone
dictation.

| | |
|---|---|
| Script | `scripts/asr.py` |
| Interpreter | skill-local `.venv/` (the script re-execs into it) |
| Server | `127.0.0.1:8081` — start via the desktop icon |
| Models | `nemotron-asr` (this skill), `audio8-tts` (out of scope) |

## Quick start

```bash
# 1. start the server (double-click the desktop icon, or:)
~/Desktop/audio-v0.8.2-audio8-perf-hotfix-bin-ubuntu-x64-vulkan/run-audiocpp.sh

# 2. check it
ASR=~/.gemini/config/skills/audiocpp-asr/scripts/asr.py
python3 $ASR doctor

# 3. transcribe
python3 $ASR transcribe lecture.mp3
python3 $ASR live                    # dictation
python3 $ASR transcribe long.wav --engine cli   # offline, no server needed
```

## Two engines

`--engine server` (default) talks to the running audio.cpp server. It supports
`--stream` and is required for `live`.

`--engine cli` shells out to `audiocpp_cli --mode offline` with the same GGUF.
**No server required**, and full-context decoding gives better accuracy on
whole files. Verified working on this machine with the server stopped:

```
$ python3 scripts/asr.py transcribe Front_Center.wav --engine cli
normalising Front_Center.wav -> 16 kHz mono...
  1.4s of audio
Front center
```

## Why `mode: "streaming"` in server.json is fine

Your config sets the ASR model to streaming mode, which is what makes live
dictation and streamed deltas possible. `mode` is model configuration, not a
request field, so it can't be flipped per call — the docs list no `mode` request
parameter, the WebUI's own ASR call sends only `{model, audio, language, options}`,
and `POST /v1/models/load` returns 403 while `ui_management` is off.

Nothing to change. Use `--engine cli` when you want offline accuracy.

## Audio normalisation

This machine has no ffmpeg and no sox, so the skill uses GStreamer
(`uridecodebin3 ! audioconvert ! audioresample ! wavenc`) to produce 16 kHz mono
s16 WAV. That's genuinely required: the server only decodes MP3/FLAC natively if
built with the `audio_decode` frontend module, and the default build has none.

Files that are already 16 kHz mono are passed through untouched.

## Tests

```bash
python3 scripts/test_asr.py
```

22 tests, fully offline. Includes a raw-socket stub for the chunked live protocol
and real GStreamer resampling checks.
