#!/usr/bin/env bash
# make-voice-ref — record a 16 kHz reference clip for Audio8 TTS voice cloning.
#
#   ./make-voice-ref.sh my-voice.wav [seconds]
#
# Audio8 clones a voice from a short reference plus its exact transcript, so
# the transcript matters more than the audio quality. After recording, run
#
#   MIC_FILE=my-voice.wav PORT=8081 REF_TEXT="what you just said" mic-tts.sh
#
# to hear the clone before wiring it into mic-tts.sh.
set -euo pipefail

OUT="${1:-my-voice-ref.wav}"
SECS="${2:-12}"
RATE=16000

[ -t 1 ] && { B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'; } || { B=""; D=""; R=""; }
say() { printf '%s%s%s\n' "$D" "$1" "$R"; }

command -v pw-record >/dev/null || { echo "need pw-record (pipewire-utils)"; exit 1; }
command -v python3  >/dev/null || { echo "need python3"; exit 1; }

say "Recording ${SECS}s from the default mic -> ${OUT}"
say "Speak a natural, varied sentence. Avoid music, reverb and long pauses."
pw-record --raw --media-category Capture --media-role Microphone \
          --rate "$RATE" --channels 1 --format s16 - 2>/dev/null |
  head -c "$(( RATE * 2 * SECS ))" |
  python3 -c '
import sys, wave
data = sys.stdin.buffer.read()
if len(data) < 4000:
    sys.exit("too little audio captured")
w = wave.open(sys.argv[1], "wb")
w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(sys.argv[2]))
w.writeframes(data); w.close()
a = memoryview(data).cast("h")
print(f"wrote {sys.argv[1]}: {len(data)/2/int(sys.argv[2]):.1f}s, "
      f"peak {max(max(a), -min(a))} (want 3000-25000)")
' "$OUT" "$RATE"

say ""
say "Now type the EXACT sentence you said and test it:"
say "  REF_TEXT=\"...\" VOICE_REF=\"$PWD/$OUT\" MIC_FILE=\"$PWD/$OUT\" \\"
say "    ~/Desktop/mic-tts.sh"
