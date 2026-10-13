#!/usr/bin/env python3
"""Unit tests for the clause committer in mic-tts.py (no audio, no server)."""
import importlib.util as ilu
import os
import queue
import sys
import threading

os.environ["VERBOSE"] = "0"
os.environ["PORT"] = "1"          # never contacted; server_up() is patched
os.environ["MIC_FILE"] = "/dev/null"

SRC = "/home/rodri/Desktop/mic-tts.py"
spec = ilu.spec_from_file_location("mic_tts", SRC)
m = ilu.module_from_spec(spec)

# The module defines its own server_up() and mic pickers at import time, so
# stub the layer underneath them: a fake HTTP connection that answers /health.
import http.client


class _Resp:
    status = 200

    def read(self):
        return b'{"status":"ok"}'

    def close(self):
        pass


class _Conn:
    def __init__(self, *a, **k):
        pass

    def request(self, *a, **k):
        pass

    def getresponse(self):
        return _Resp()

    def close(self):
        pass


m.__dict__  # module not executed yet
import http.client as _hc
_hc.HTTPConnection = _Conn
m.list_sources = lambda: []
m.pick_source = lambda: "auto"


class FakePlayer:
    def __init__(self):
        self.q = queue.Queue()
        self.playing = threading.Event()

    def submit(self, p):
        pass

    def start(self):
        pass

    def stop_now(self):
        pass


m.Player = FakePlayer
spec.loader.exec_module(m)
C = m.Committer

fails = []


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        print(f"          got  {got!r}")
        print(f"          want {want!r}")
        fails.append(name)


print("\n1. a clause commits only once the guard is satisfied")
c = C()
check("partial, no punctuation", c.feed("This is a"), [])
check("trailing '.' with nothing after it waits", c.feed("This is a demo of it."), [])
check("guard still short (8 chars after)", c.feed("This is a demo of it. And then"), [])
check("guard satisfied (21 chars after)", c.feed("This is a demo of it. And then it was over."),
      ["This is a demo of it."])

print("\n2. a comma gives early audio mid-sentence")
c = C()
check("no comma yet", c.feed("I went to the store"), [])
check("comma, guard short", c.feed("I went to the store, and"), [])
check("guard satisfied", c.feed("I went to the store, and bought milk."),
      ["I went to the store,"])

print("\n3. unpunctuated text waits for the flush")
c = C()
check("growing", c.feed("no commas here at all"), [])
check("flush", c.flush(), ["no commas here at all"])

print("\n4. fragments shorter than COMMIT_MIN_CHARS are dropped")
c = C()
check("tiny clauses", c.feed("Hi. Ok. So anyway I went outside today."), [])

print("\n5. flush is idempotent - never speaks the same text twice")
c = C()
check("trailing clause not yet committed", c.feed("Hello there my friend. "), [])
check("flush speaks it once", c.flush(), ["Hello there my friend."])
check("flush again is a no-op", c.flush(), [])

print("\n6. a full paragraph streams out in order, once each")
c = C()
out = []
for h in ["Well ", "Well I ", "Well I think ", "Well I think it ",
          "Well I think it works. ", "Well I think it works. Give it a shot then."]:
    out += c.feed(h)
out += c.flush()
check("clauses", out, ["Well I think it works.", "Give it a shot then."])

print("\n7. markdown/noise from ASR is stripped before synthesis")
c = C()
check("asterisks", c.feed("*hello* **there** friend. ok then we left"),
      ["hello there friend."])

print("\n8. repeated feeds never re-emit a spoken clause")
c = C()
check("first sentence still open", c.feed("One thing happened. "), [])
check("first sentence commits", c.feed("One thing happened. Two things happened. "),
      ["One thing happened."])
check("neither is repeated", c.feed("One thing happened. Two things happened. Then we left. "),
      ["Two things happened."])

print("\n9. a hypothesised revision before commit is not spoken twice")
c = C()
first = c.feed("I went to the store, and bought mi")
# ASR revises the tail: the committed part is untouched
second = c.feed("I went to the store, and bought milk")
check("revised tail only", second, [])

print(f"\n{'ALL TESTS PASSED' if not fails else f'{len(fails)} FAILED: {fails}'}\n")
sys.exit(1 if fails else 0)
