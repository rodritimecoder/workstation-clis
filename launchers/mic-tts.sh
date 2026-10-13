#!/usr/bin/env bash
# mic-tts — speak, and hear yourself back in your own voice.
#
#   ./mic-tts.sh
#
# Streams your speech through nemotron-asr on the local audio.cpp server, and
# speaks each settled clause back through Audio8 TTS. The default voice is the
# server's 'maomao' preset (/run/media/rodri/AI/voice/maomao.wav, defined in
# server.json). The
# first sentence is already playing while you are still talking.
# Ctrl-C to exit.
#
# Start the audio.cpp server first: Desktop icon 'audio.cpp Server'.
#
# Env knobs:
#   PORT=8081              audio.cpp port
#   ASR_MODEL=nemotron-asr
#   ASR_LANG=en-US
#   TTS_MODEL=audio8-tts
#   VOICE_PRESET=maomao    named voice preset configured in server.json
#   VOICE_REF=<file.wav>   16 kHz mono clip to clone from instead of a preset
#   REF_TEXT="..."         the exact words said in VOICE_REF
#   MIC_TARGET=auto        auto | a substring of the pw-cli source name
#   MIC_FILE=clip.wav      use a 16 kHz mono WAV instead of the mic
#   END_SILENCE=0.45       seconds of quiet that end an utterance
#   PREROLL=0.25           audio kept before the first detected word
#   GATE_THRESH=320        speech threshold in s16 units (~-50 dBFS)
#   COMMIT_GUARD=12        chars that must follow a clause mark before speaking
#   COMMIT_MIN_CHARS=12    never speak a clause shorter than this
#   BARGE_IN=1             let speech interrupt the TTS (use headphones!)
#   VERBOSE=1              per-clause latency logging
#
# To use your own voice, record a reference first:
#   ./make-voice-ref.sh my-voice.wav
# then export VOICE_REF=... REF_TEXT="..."
# Or point VOICE_PRESET at another preset in server.json (e.g. alloy).

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PORT="${PORT:-8081}"
export VOICE_REF="${VOICE_REF:-}"
export REF_TEXT="${REF_TEXT:-}"

command -v python3 >/dev/null || { echo "need python3"; exit 1; }

if ! curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "audio.cpp server is not answering on ${PORT}."
  echo "start it first: Desktop icon 'audio.cpp Server'"
  exit 1
fi

exec python3 "${APP_DIR}/mic-tts.py" "$@"
