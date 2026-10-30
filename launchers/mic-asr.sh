#!/usr/bin/env bash
# mic-asr — barebones streaming dictation against the local audio.cpp server.
#
#   ./mic-asr.sh
#
# Talk, pause, and it finalises the sentence and goes back to listening.
# Words stream in as they are decoded; the final transcript then replaces them.
# Ctrl-C to exit.
#
# Env knobs:
#   ASR_PORT=8081        audio.cpp port
#   ASR_MODEL=nemotron-asr
#   ASR_LANG=en-US       any of the 40 locales nemotron_asr supports
#   MIC_TARGET=auto      auto (pick a mic for you) | a pw-record target name
#   MIC_FILE=clip.wav    transcribe a 16 kHz mono WAV instead of the mic
#   END_SILENCE=0.7      seconds of quiet that end an utterance
#   MAX_UTT=25           hard cap on one utterance
#   MAX_WAIT=20          give up if nothing is said in this long
#   PREROLL=0.25         audio kept before the first detected word
#   GATE_THRESH=320      speech threshold in s16 units (~-50 dBFS)
#   GATE_DEBUG=1         show endpointing decisions

PORT="${ASR_PORT:-8081}"
MODEL="${ASR_MODEL:-nemotron-asr}"
LANG_CODE="${ASR_LANG:-en-US}"
END_SILENCE="${END_SILENCE:-0.5}"
MAX_UTT="${MAX_UTT:-25}"
MAX_WAIT="${MAX_WAIT:-20}"
PREROLL="${PREROLL:-0.25}"
GATE_THRESH="${GATE_THRESH:-320}"
TARGET="${MIC_TARGET:-topping}"
MIC_FILE="${MIC_FILE:-}"
URL="http://127.0.0.1:${PORT}/v1/audio/transcriptions/live?model=${MODEL}&sample_rate=16000&channels=1&sample_format=s16le&language=${LANG_CODE}"

if [ -t 1 ]; then B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'; C=$'\033[2K\r'; Y=$'\033[33m'; else B=""; D=""; R=""; C=$'\n'; Y=""; fi
say() { printf '%s%s%s\n' "$D" "$1" "$R"; }
die() { printf '%s%s%s\n' "$Y" "$1" "$R"; exit 1; }

command -v python3 >/dev/null || die "need python3"
command -v curl    >/dev/null || die "need curl"
[ -z "$MIC_FILE" ] && command -v pw-record >/dev/null || true
[ -n "$MIC_FILE" ] || command -v pw-record >/dev/null || die "need pw-record (pipewire-utils)"

curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 || {
  say "audio.cpp server is not answering on ${PORT}."
  say "start it first: Desktop icon 'audio.cpp Server', or"
  say "  /run/media/rodri/AI/audio.cpp/run-audiocpp.sh"
  exit 1
}

# ------------------------------------------------------------- pick a mic
read -r -d '' PICK <<'PYEOF' || true
import sys, re
txt = sys.stdin.read()
srcs = []
for blk in re.split(r"\n\s*id \d+, type", txt):
    d = dict(re.findall(r"node\.(name|description)\s*=\s*\"([^\"]*)\"", blk))
    d = {("node." + k): v for k, v in d.items()}
    if "Source" not in blk:
        continue
    name = d.get("node.name", "")
    desc = d.get("node.description", "")
    if "monitor" in name.lower() or "monitor" in desc.lower():
        continue
    srcs.append((name, desc))
if not srcs:
    raise SystemExit
mics = [s for s in srcs if re.search(r"mic", s[0] + s[1], re.I)]
ins = [s for s in srcs if re.search(r"input|capture", s[0] + s[1], re.I)]
ordered = mics + [s for s in ins if s not in mics] + [s for s in srcs if s not in mics and s not in ins]
for name, _ in ordered:
    print(name)
PYEOF

probe_peak() {  # peak amplitude of 0.6s from a pw-record target
  timeout 0.7 pw-record --raw --target "$1" --rate 16000 --channels 1 --format s16 - 2>/dev/null \
    | python3 -c "
import sys, array
d = sys.stdin.buffer.read()
if len(d) < 2:
    print(0); raise SystemExit
a = array.array('h'); a.frombytes(d[:len(d) // 2 * 2])
print(max(max(a), -min(a)))
" 2>/dev/null || echo 0
}

list_sources() { pw-cli ls Node 2>/dev/null | python3 -c "$PICK" 2>/dev/null; }

resolve_target() {  # first source whose name contains $1 (case-insensitive)
  local q="${1,,}" c
  while read -r c; do
    [ -z "$c" ] && continue
    case "${c,,}" in *"$q"*) printf '%s\n' "$c"; return 0 ;; esac
  done < <(list_sources)
  return 1
}

pick_source() {
  # Prefer a mic that actually carries signal; fall back to the loudest one seen.
  local c best="" bestpeak=0 peak
  while read -r c; do
    [ -z "$c" ] && continue
    peak="$(probe_peak "$c")"
    peak="${peak:-0}"
    case "$peak" in (*[!0-9]*) peak=0 ;; esac
    if [ "$peak" -gt "$bestpeak" ]; then best="$c"; bestpeak="$peak"; fi
  done <<< "$(list_sources)"
  printf '%s\n' "$best"
}

want=""
if [ -n "$MIC_FILE" ]; then
  say "input: ${MIC_FILE} (file)"
elif [ "$TARGET" != "auto" ]; then
  want="$TARGET"
  if ! TARGET="$(resolve_target "$want")"; then
    printf '%sno source matching "%s"%s\n' "$Y" "$want" "$R"
    say "available:"
    list_sources | sed 's/^/  /'
    exit 1
  fi
  say "mic: ${TARGET}"
  say "override with MIC_TARGET=<substring>  (e.g. MIC_TARGET=mic1)"
elif [ "$TARGET" = "auto" ]; then
  TARGET="$(pick_source)"
  if [ -n "$TARGET" ]; then
    say "mic: ${TARGET}"
    say "override with MIC_TARGET=<name>  (pw-cli ls Node | grep -i source)"
  else
    TARGET="auto"
    say "mic: pipewire default source"
  fi
fi

# ------------------------------------------------------------- silence gate
# s16le 16 kHz mono in, same out: hold back leading silence, close the stream
# when the speaker stops. Exit 3 means "nothing was said" (no audio forwarded).
read -r -d '' GATE <<'PY' || true
import os, sys, array
RATE = 16000
END = float(os.environ["END_SILENCE"])
MAX = float(os.environ["MAX_UTT"])
WAIT = float(os.environ["MAX_WAIT"])
PRE = float(os.environ["PREROLL"])
THRESH = int(os.environ["GATE_THRESH"])
DBG = os.environ.get("GATE_DEBUG") == "1"
CHUNK = 1024
PRE_N = max(1, int(PRE * RATE / CHUNK))
MAX_N = int(MAX * RATE / CHUNK)
END_N = max(1, int(END * RATE / CHUNK))
WAIT_N = int(WAIT * RATE / CHUNK)

def dbg(m):
    if DBG:
        sys.stderr.write("[gate] %s\n" % m); sys.stderr.flush()

def emit(buf):
    if not buf:
        return
    try:
        sys.stdout.buffer.write(b"".join(buf)); sys.stdout.buffer.flush()
    except BrokenPipeError:
        raise SystemExit(0)

pre, out = [], []
speaking = False
quiet = frames = 0

while True:
    data = sys.stdin.buffer.read(CHUNK * 2)
    if not data or len(data) < CHUNK * 2:
        break
    a = array.array("h"); a.frombytes(data)
    loud = max(abs(min(a)), abs(max(a))) > THRESH
    frames += 1

    if not speaking:
        if loud:
            speaking = True
            dbg("speech at %.2fs" % (frames * CHUNK / RATE))
            emit(pre + [data])
            pre, quiet = [], 0
        else:
            pre.append(data)
            if len(pre) > PRE_N:
                del pre[0]
            if frames >= WAIT_N:
                dbg("nothing heard in %.0fs" % WAIT)
                raise SystemExit(3)
    else:
        out.append(data)
        emit([data])            # forward immediately: the server needs to see it live
        quiet = 0 if loud else quiet + 1
        if quiet >= END_N:
            dbg("utterance ends at %.2fs" % (frames * CHUNK / RATE)); break
        if len(out) >= MAX_N:
            dbg("max length"); break

if not speaking:
    raise SystemExit(3)
dbg("sent %d frames" % len(out))
PY

# ---------------------------------------------------------------- SSE print
read -r -d '' PRINT <<'AWK' || true
BEGIN { ORS = ""; part = "" }
/"transcript.text.delta"/ {
    s = $0
    sub(/^.*"delta":"/, "", s); sub(/"}.*$/, "", s)
    gsub(/\\n/, " ", s); gsub(/\\"/, "\"", s); gsub(/\\\\/, "\\", s)
    part = part s
    printf "%s", s
    fflush()
    next
}
/"transcript.text.done"/ {
    s = $0
    sub(/^.*"text":"/, "", s)
    sub(/","timing".*$/, "", s); sub(/"}.*$/, "", s); sub(/"[},].*$/, "", s)
    gsub(/\\n/, " ", s); gsub(/\\"/, "\"", s); gsub(/\\\\/, "\\", s)
    printf "%s%s%s%s\n", C, B, s, R
    fflush()
    next
}
AWK

# ------------------------------------------------------------------- capture
capture() {
  if [ -n "$MIC_FILE" ]; then
    case "$MIC_FILE" in
      *.wav|*.WAV) python3 -c '
import os, sys, wave
try:
    w = wave.open(sys.argv[1])
    if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
        sys.exit("want 16 kHz mono 16-bit")
    while True:
        d = w.readframes(4096)
        if not d:
            break
        sys.stdout.buffer.write(d)
        sys.stdout.buffer.flush()
except BrokenPipeError:
    pass
try:
    sys.stdout.close()
except BrokenPipeError:
    os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
' "$MIC_FILE" ;;
      *) cat "$MIC_FILE" ;;
    esac
  else
    pw-record --raw --media-category Capture --media-role Microphone \
              --target "$TARGET" --rate 16000 --channels 1 --format s16 - 2>/dev/null
  fi
}

say "mic-asr — ${MODEL} | ${LANG_CODE} | port ${PORT}"
say "latency: lookahead 0 (set in server.json) | endpoint ${END_SILENCE}s | pre-roll ${PREROLL}s"
say "Ctrl-C to quit."
trap 'printf "\n"; exit 0' INT
trap 'exit 0' TERM

while :; do
  printf '%s' "${D}… listening${R}"
  capture \
  | END_SILENCE="$END_SILENCE" MAX_UTT="$MAX_UTT" MAX_WAIT="$MAX_WAIT" \
         PREROLL="$PREROLL" GATE_THRESH="$GATE_THRESH" GATE_DEBUG="$GATE_DEBUG" \
    python3 -c "$GATE" \
  | curl -N -sS -X POST -H 'Expect:' -T - "$URL" \
  | awk -v B="$B" -v D="$D" -v R="$R" -v C="$C" "$PRINT"

  # PIPESTATUS[1] is the gate: 3 means it never heard anything, so nothing was sent
  st=("${PIPESTATUS[@]}")
  if [ "${st[1]}" = "3" ]; then
    printf '%s(nothing heard)%s\n' "$D" "$R"
  else
    printf '\n'
  fi
  sleep 0.2
done
