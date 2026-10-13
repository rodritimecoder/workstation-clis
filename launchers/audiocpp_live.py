#!/usr/bin/env python3
"""Bidirectional chunked HTTP + SSE client for audio.cpp live endpoints."""
import json
import socket


class LiveStream:
    """POST a chunked request body while reading an SSE response concurrently.

    http.client cannot do this: request() buffers the whole generator, and
    getresponse() may not be called until the body is finished. A raw socket
    can, which is what makes real-time ASR possible.
    """

    def __init__(self, host, port, path, ctype="application/octet-stream",
                 timeout=300.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.25)
        self.buf = b""
        req = (f"POST {path} HTTP/1.1\r\n"
               f"Host: {host}:{port}\r\n"
               f"Content-Type: {ctype}\r\n"
               f"Accept: text/event-stream\r\n"
               f"Transfer-Encoding: chunked\r\n"
               f"\r\n").encode()
        self.sock.sendall(req)
        self.status, self._resp_chunked = self._read_headers()

    def _read_headers(self):
        while b"\r\n\r\n" not in self.buf:
            d = self.sock.recv(65536)
            if not d:
                raise ConnectionError("server closed during headers")
            self.buf += d
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        status = int(lines[0].split()[1])
        hdrs = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                hdrs[k.strip().lower()] = v.strip()
        return status, hdrs.get("transfer-encoding", "").lower() == "chunked"

    # ---------------------------------------------------------------- write
    def send(self, data: bytes):
        self.sock.sendall(b"%x\r\n" % len(data) + data + b"\r\n")

    def end(self):
        self.sock.sendall(b"0\r\n\r\n")

    # ----------------------------------------------------------------- read
    def _fill(self, deadline):
        import time
        while time.time() < deadline:
            try:
                d = self.sock.recv(65536)
                if not d:
                    return False
                self.buf += d
                return True
            except socket.timeout:
                continue
        return False

    def _read_line(self, deadline):
        while b"\r\n" not in self.buf:
            if not self._fill(deadline):
                return None
        line, self.buf = self.buf.split(b"\r\n", 1)
        return line

    def _read_exact(self, n, deadline):
        while len(self.buf) < n:
            if not self._fill(deadline):
                return None
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def events(self, idle_timeout=600.0):
        """Yield parsed SSE payload dicts until [DONE] or the server closes.

        Each HTTP chunk *contains* the SSE event text, so the payload is
        decoded first and only then split into lines.
        """
        import time
        deadline = time.time() + idle_timeout
        pending = b""
        while True:
            if self._resp_chunked:
                size_line = self._read_line(deadline)
                if size_line is None:
                    return
                if not size_line:
                    continue
                try:
                    n = int(size_line.split(b";")[0], 16)
                except ValueError:
                    continue
                if n == 0:
                    return
                payload = self._read_exact(n, deadline)
                if payload is None:
                    return
                if self._read_exact(2, deadline) is None:      # chunk CRLF
                    return
                pending += payload
            else:
                payload = self._read_line(deadline)
                if payload is None:
                    return
                pending += payload + b"\n"

            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                raw = raw.strip()
                if not raw.startswith(b"data:"):
                    continue
                p = raw[5:].strip()
                if p == b"[DONE]":
                    return
                try:
                    yield json.loads(p)
                except json.JSONDecodeError:
                    continue

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
