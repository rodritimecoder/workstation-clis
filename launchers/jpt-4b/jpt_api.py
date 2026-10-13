#!/usr/bin/env python3
"""System One-compatible HTTP facade for JPT-4B on llama.cpp.

Serves the same wire format as llm2jev (https://docs.typesafe.ai/api) so one client can
point at either decision model:

    POST /v1/systemone   {"state": ..., "questions": {qid: {...}}} -> {"answers": {qid: {...}}}
    GET  /health         {"status": "ok", "model": ...}
    GET  /               short index

One llama-server holds the weights; this process only renders and reads label logprobs,
so it is cheap and safe to leave running.

    python3 jpt_api.py --port 8080 --engine http://127.0.0.1:8090
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jpt_llamacpp import JPTError, JPTLlamaCpp

ENGINE_LOCK = threading.Lock()   # one llama.cpp slot -> serialise decisions


class Handler(BaseHTTPRequestHandler):
    engine: JPTLlamaCpp = None
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        body = json.dumps(obj, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", ""):
            ok = self.engine.health()
            info = self.engine.info() if ok else {}
            self._send(200 if ok else 503, {"status": "ok" if ok else "loading", **info})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/systemone":
            self._send(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            state = req.get("state", "")
            questions = req.get("questions") or {}
            if not isinstance(questions, dict) or not questions:
                raise JPTError("questions must be a non-empty object of question id -> question")
            with ENGINE_LOCK:
                answers = self.engine.decide(state, questions,
                                             temperature=req.get("temperature"))
            meta = answers.pop("_meta", {})
            self._send(200, {"answers": answers, "meta": meta})
        except JPTError as e:
            self._send(400, {"error": str(e)})
        except json.JSONDecodeError as e:
            self._send(400, {"error": f"bad JSON: {e}"})
        except Exception as e:  # noqa: BLE001 - surface engine failures to the caller
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *a):
        if os.environ.get("JPT_API_VERBOSE"):
            super().log_message(fmt, *a)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=int(os.environ.get("JPT_PORT", 8080)))
    ap.add_argument("--engine", default=os.environ.get("JPT_ENGINE_URL", "http://127.0.0.1:8090"))
    ap.add_argument("--temperature", type=float,
                    default=float(os.environ.get("JPT_TEMPERATURE", 1.036)))
    a = ap.parse_args()

    engine = JPTLlamaCpp(a.engine, temperature=a.temperature)
    if not engine.health():
        raise SystemExit(f"llama-server not healthy at {a.engine} — start it first (start-jpt.sh does)")
    Handler.engine = engine
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"jpt-4b System One API on http://127.0.0.1:{a.port}/v1/systemone  (engine {a.engine})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()