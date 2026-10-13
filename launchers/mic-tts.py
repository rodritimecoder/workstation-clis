#!/usr/bin/env python3
"""
mic-tts — speak, and hear yourself back in your own voice.

Everything runs locally on one audio.cpp server (Vulkan backend):

    mic ──VAD──▶ /v1/audio/transcriptions/live ──▶ committed clauses
                                                        │
                                   /v1/audio/speech ◀───┘   Audio8 TTS, voice clone
                                                        │
                                                   pw-play ▶ speakers

ASR partials are append-only but still get revised, so we never speak a raw
delta. We speak *committed clauses*: text ending in punctuation that has since
settled by COMMIT_GUARD characters. The tail is flushed on the final transcript.

See mic-tts.sh for the environment knobs.
"""
import http.client
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audiocpp_live import LiveStream

PORT = int(os.environ.get("PORT", "8081"))
ASR_MODEL = os.environ.get("ASR_MODEL", "nemotron-asr")
ASR_LANG = os.environ.get("ASR_LANG", "en-US")
TTS_MODEL = os.environ.get("TTS_MODEL", "audio8-tts")
# Voice selection. By default we send the server's named preset ("maomao"),
# which is also server.json's default_voice_preset, so there is one source of
# truth. Set VOICE_REF to a 16 kHz mono clip to clone from that instead.
VOICE_PRESET = os.environ.get("VOICE_PRESET", "maomao")
VOICE_REF = os.environ.get("VOICE_REF", "")
REF_TEXT = os.environ.get("REF_TEXT", "")
MIC_FILE = os.environ.get("MIC_FILE", "")
MIC_TARGET = os.environ.get("MIC_TARGET", "auto")

END_SILENCE = float(os.environ.get("END_SILENCE", "0.45"))
MAX_UTT = float(os.environ.get("MAX_UTT", "30"))
MAX_WAIT = float(os.environ.get("MAX_WAIT", "20"))
PREROLL = float(os.environ.get("PREROLL", "0.25"))
GATE_THRESH = int(os.environ.get("GATE_THRESH", "320"))
COMMIT_GUARD = int(os.environ.get("COMMIT_GUARD", "12"))
COMMIT_MIN_CHARS = int(os.environ.get("COMMIT_MIN_CHARS", "12"))
BARGE_IN = os.environ.get("BARGE_IN", "1") == "1"
VERBOSE = os.environ.get("VERBOSE", "1") == "1"

RATE = 16000
CHUNK = 1024
CLAUSE_END = re.compile(r"[.!?…]+[\"'”’)\]]*\s+|[,;:—]+\s+")

if sys.stdout.isatty():
    B, DIM, RST, YEL, CLR = "\033[1m", "\033[2m", "\033[0m", "\033[33m", "\033[2K\r"
else:
    B = DIM = RST = YEL = ""
    CLR = "\n"


def say(m):
    print(f"{DIM}{m}{RST}", flush=True)


def warn(m):
    print(f"{YEL}{m}{RST}", flush=True)


def log(m):
    if VERBOSE:
        print(f"{DIM}      {m}{RST}", flush=True)


# ------------------------------------------------------------------ plumbing
def server_up():
    try:
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=3)
        c.request("GET", "/health")
        ok = c.getresponse().status == 200
        c.close()
        return ok
    except Exception:
        return False


if not server_up():
    warn(f"audio.cpp server is not answering on {PORT}.")
    warn("start it first: Desktop icon 'audio.cpp Server'")
    sys.exit(1)

if shutil.which("pw-play") is None:
    warn("need pw-play (pipewire-utils) for output")
    sys.exit(1)


# ----------------------------------------------------------------- mic target
def list_sources():
    txt = subprocess.run(["pw-cli", "ls", "Node"], capture_output=True,
                         text=True).stdout
    out = []
    for blk in re.split(r"\n\s*id \d+, type", txt):
        d = dict(re.findall(r'node\.(name|description)\s*=\s*"([^"]*)"', blk))
        if "Source" not in blk:
            continue
        name, desc = d.get("name", ""), d.get("description", "")
        if "monitor" in (name + desc).lower():
            continue
        out.append(name)
    return out


def probe_peak(target):
    try:
        p = subprocess.run(
            ["timeout", "0.7", "pw-record", "--raw", "--target", target,
             "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
            capture_output=True, timeout=3)
        d = p.stdout
        if len(d) < 2:
            return 0
        a = memoryview(d).cast("h")
        return max(max(a), -min(a))
    except Exception:
        return 0


def pick_source():
    best, bestpeak = "", 0
    for n in list_sources():
        pk = probe_peak(n)
        if pk > bestpeak:
            best, bestpeak = n, pk
    return best


TARGET = ""
if MIC_FILE:
    say(f"input: {MIC_FILE}")
else:
    if MIC_TARGET == "auto":
        TARGET = pick_source() or "auto"
    else:
        TARGET = next((n for n in list_sources()
                       if MIC_TARGET.lower() in n.lower()), None)
        if not TARGET:
            warn(f'no source matching "{MIC_TARGET}"')
            for n in list_sources():
                say(f"  {n}")
            sys.exit(1)
    say(f"mic: {TARGET}")

_voice_desc = os.path.basename(VOICE_REF) if VOICE_REF else f"preset '{VOICE_PRESET}'"
say(f"tts: {TTS_MODEL} | voice: {_voice_desc} | port {PORT}")
say(f"commit guard {COMMIT_GUARD}ch | endpoint {END_SILENCE}s | "
    f"barge-in {'on' if BARGE_IN else 'off'}")
say("Ctrl-C to quit.\n")

TMPDIR = tempfile.mkdtemp(prefix="mic-tts-")
STOP = threading.Event()


# ------------------------------------------------------------------- playback
class Player(threading.Thread):
    """Serial WAV playback with instant abort."""

    def __init__(self):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.proc = None
        self.lock = threading.Lock()
        self.playing = threading.Event()
        self.idle = threading.Event()
        self.idle.set()

    def submit(self, path):
        self.idle.clear()
        self.q.put(path)

    def stop_now(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        while True:
            try:
                os.unlink(self.q.get_nowait())
            except queue.Empty:
                break
            except OSError:
                pass

    def run(self):
        while not STOP.is_set():
            try:
                path = self.q.get(timeout=0.2)
            except queue.Empty:
                self.idle.set()
                continue
            with self.lock:
                self.proc = None
            self.playing.set()
            try:
                with self.lock:
                    self.proc = subprocess.Popen(
                        ["pw-play", path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    rc = self.proc.wait()
                if rc not in (0, -15, 143):
                    warn(f"pw-play exited {rc}")
            except Exception as e:
                warn(f"playback failed: {e}")
            finally:
                self.playing.clear()
                with self.lock:
                    self.proc = None
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if self.q.empty():
                self.idle.set()


player = Player()
player.start()


# ---------------------------------------------------------------------- synth
def tts_speak(text):
    """Render one clause. Returns (path, duration_s) or None."""
    body = {"model": TTS_MODEL, "input": text, "response_format": "wav"}
    if VOICE_REF:
        # Explicit clone from a user-supplied clip.
        body["voice"] = "clone"
        body["voice_ref"] = VOICE_REF
        body["reference_text"] = REF_TEXT
    else:
        # Use a voice preset configured on the server (maomao by default).
        body["voice"] = VOICE_PRESET
    try:
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=180)
        c.request("POST", "/v1/audio/speech", json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        data = r.read()
        c.close()
    except Exception as e:
        warn(f"tts request failed: {e}")
        return None
    if not data.startswith(b"RIFF"):
        try:
            msg = json.loads(data).get("error", {}).get("message", data[:120])
        except Exception:
            msg = data[:120]
        warn(f"tts rejected: {msg}")
        return None
    fd, path = tempfile.mkstemp(suffix=".wav", dir=TMPDIR)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    try:
        with wave.open(path) as w:
            dur = w.getnframes() / float(w.getframerate())
    except Exception:
        dur = 0.0
    return path, dur


class Synth(threading.Thread):
    daemon = True

    def __init__(self):
        super().__init__()
        self.q = queue.Queue()
        self.idle = threading.Event()
        self.idle.set()

    def submit(self, text):
        self.idle.clear()
        self.q.put(text)

    def run(self):
        while not STOP.is_set():
            try:
                text = self.q.get(timeout=0.2)
            except queue.Empty:
                self.idle.set()
                continue
            t0 = time.time()
            res = tts_speak(text)
            if res:
                path, dur = res
                log(f"rendered {dur:4.1f}s of audio in {time.time()-t0:4.2f}s")
                player.submit(path)
            if self.q.empty():
                self.idle.set()


synth = Synth()
synth.start()


# --------------------------------------------------------------------- commit
def clean_for_tts(s):
    s = re.sub(r"[*_`#>\[\]]", "", s)
    return re.sub(r"\s+", " ", s).strip()


class Committer:
    """Cumulative ASR hypothesis -> speakable clauses."""

    def __init__(self):
        self.hyp = ""
        self.spoken = 0

    def feed(self, text):
        self.hyp = text
        out = []
        while True:
            m = CLAUSE_END.search(self.hyp, self.spoken)
            if not m:
                break
            end = m.end()
            if len(self.hyp) - end < COMMIT_GUARD:
                break                      # punctuation still being extended
            piece = clean_for_tts(self.hyp[self.spoken:end])
            self.spoken = end
            if len(piece) >= COMMIT_MIN_CHARS:
                out.append(piece)
        return out

    def flush(self):
        rest = clean_for_tts(self.hyp[self.spoken:])
        self.spoken = len(self.hyp)
        return [rest] if len(rest) >= 4 else []


# ----------------------------------------------------------------------- ASR
def run_utterance(committed):
    """Capture one utterance and stream it to the ASR while it is happening.

    The mic is piped into the live endpoint in real time (a raw socket is used
    because http.client buffers the request body and cannot read the response
    at the same time). Clauses are committed and synthesised as the transcript
    grows, so the first audio overlaps the tail of the speech.

    Returns (final_text, bailed_out).
    """
    url = (f"/v1/audio/transcriptions/live?model={ASR_MODEL}&sample_rate={RATE}"
           f"&channels=1&sample_format=s16le&language={ASR_LANG}")
    state = {"barge": False, "error": None, "t0": time.time()}

    try:
        st = LiveStream("127.0.0.1", PORT, url)
    except Exception as e:
        warn(f"asr connect failed: {e}")
        return None, False
    if st.status != 200:
        warn(f"asr returned {st.status}")
        st.close()
        return None, False

    def feeder():
        try:
            for item in capture_utterance():
                if item == "barge":
                    state["barge"] = True
                    player.stop_now()
                    break
                st.send(item)
            st.end()
        except Exception as e:
            state["error"] = e

    th = threading.Thread(target=feeder, daemon=True)
    th.start()

    hyp, final, t_first = "", None, None
    try:
        for ev in st.events():
            kind = ev.get("type", "")
            if kind == "transcript.text.delta":
                if t_first is None:
                    t_first = time.time() - state["t0"]
                    log(f"first partial {t_first*1000:.0f}ms into the utterance")
                hyp += ev.get("delta", "")
                for clause in committed.feed(hyp):
                    print(f"{DIM}you: {clause}{RST}", end=" ", flush=True)
                    synth.submit(clause)
            elif kind == "transcript.text.done":
                final = ev.get("text")
    finally:
        th.join(timeout=3)
        st.close()

    if state["error"]:
        warn(f"asr stream error: {state['error']}")
    return (final if final is not None else hyp), state["barge"]


# -------------------------------------------------------------------- capture
def capture_utterance():
    """Yield gated s16le blocks: preroll, then live while speech continues.

    Sets `barge` when the user talks over TTS that is currently playing.
    """
    pre, frames, quiet, speaking = [], 0, 0, False
    end_n = max(1, int(END_SILENCE * RATE / CHUNK))
    wait_n = max(1, int(MAX_WAIT * RATE / CHUNK))
    max_n = int(MAX_UTT * RATE / CHUNK)
    pre_n = max(1, int(PREROLL * RATE / CHUNK))

    if MIC_FILE:
        with wave.open(MIC_FILE) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
                warn("MIC_FILE must be 16 kHz mono 16-bit")
                return
            while not STOP.is_set():
                d = w.readframes(CHUNK)
                if not d:
                    return
                yield d
                time.sleep(len(d) / (RATE * 2))   # pace it like real speech
        return

    proc = subprocess.Popen(
        ["pw-record", "--raw", "--media-category", "Capture",
         "--media-role", "Microphone", "--target", TARGET,
         "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    try:
        while not STOP.is_set():
            data = proc.stdout.read(CHUNK * 2)
            if not data or len(data) < CHUNK * 2:
                return
            a = memoryview(data).cast("h")
            loud = max(max(a), -min(a)) > GATE_THRESH
            frames += 1
            if not speaking:
                if loud:
                    speaking = True
                    quiet = 0
                    for b in pre:
                        yield b
                    pre = []
                    yield data
                else:
                    pre.append(data)
                    if len(pre) > pre_n:
                        pre.pop(0)
                    if frames >= wait_n:
                        return
            else:
                yield data
                if BARGE_IN and loud and player.playing.is_set():
                    return "barge"
                quiet = 0 if loud else quiet + 1
                if quiet >= end_n or frames >= max_n:
                    return
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass


# ------------------------------------------------------------------------ main
def main():
    while not STOP.is_set():
        print(f"{DIM}… listening{RST}", end="", flush=True)
        committed = Committer()
        t_utt = time.time()
        final, bailed = run_utterance(committed)
        print(CLR, end="", flush=True)

        if bailed:
            drop_pending(synth.q)     # unsent clauses
            drop_pending(player.q)     # rendered wav files that never played
            print(f"{YEL}barge-in — TTS cut off{RST}", flush=True)
            time.sleep(0.25)
            continue

        for clause in committed.flush():
            print(f"{DIM}you: {clause}{RST}", end=" ", flush=True)
            synth.submit(clause)

        if final:
            print(f"\n{DIM}asr ({time.time()-t_utt:.1f}s): {final}{RST}", flush=True)
        elif committed.hyp:
            print(f"\n{DIM}asr: (no final text){RST}", flush=True)
        else:
            print(f"\n{DIM}(nothing heard){RST}", flush=True)
            time.sleep(0.3)
            continue

        # let this utterance's audio finish before reopening the mic
        deadline = time.time() + 60
        while not (synth.idle.is_set() and player.idle.is_set()):
            if STOP.is_set() or time.time() > deadline:
                break
            time.sleep(0.05)


def drop_pending(q):
    """Discard queued items. Queued TTS results are wav paths, so unlink those;
    queued clauses are plain text and are simply thrown away."""
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            return
        if isinstance(item, str) and item.endswith(".wav") and os.path.exists(item):
            try:
                os.unlink(item)
            except OSError:
                pass


def shutdown(*_):
    STOP.set()
    player.stop_now()
    time.sleep(0.2)
    shutil.rmtree(TMPDIR, ignore_errors=True)
    os._exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        main()
    finally:
        shutdown()
