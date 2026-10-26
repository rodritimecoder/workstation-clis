#!/usr/bin/env python3
"""Headed Chromium with a CDP port, visible on the user's desktop.

The headless shell owns :9222 on this machine, so automation always ran in a
window nobody could see. This helper owns a second, headed Chromium profile
whose debug port is separate from the automation shell.

Commands:
  doctor          report which browser owns each port and whether it is visible
  launch          start the headed agent browser and wait for its CDP endpoint
  stop            stop only the agent browser (matched by its profile path)
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_PORT = 9224
PROFILE = os.path.expanduser("~/.local/share/chromium-agent")
FLATPAK_APP = "org.chromium.Chromium"
AUTOMATION_PORT = 9222


def cdp_version(port, timeout=1.0):
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def cdp_targets(port, timeout=1.0):
    url = f"http://127.0.0.1:{port}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return []


def chromium_processes():
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                raw = handle.read()
        except OSError:
            continue
        fields = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
        if not fields:
            continue
        joined = " ".join(fields)
        if "chrom" not in joined.lower():
            continue
        found.append((int(entry), joined))
    return found


def process_kind(joined):
    if "chrome_crashpad_handler" in joined:
        return "helper"
    if "--type=" in joined:
        return "child"
    if "chrome-headless-shell" in joined:
        return "headless"
    if joined.startswith(("/app/chromium/chrome", "/app/bin/chromium", "/opt/", "/usr/bin/chrom")):
        return "desktop"
    return "other"


def browser_processes():
    return [
        (pid, joined)
        for pid, joined in chromium_processes()
        if process_kind(joined) in ("headless", "desktop")
    ]


def flag_value(joined, name):
    marker = f"--{name}="
    index = joined.find(marker)
    if index < 0:
        return None
    rest = joined[index + len(marker):]
    return rest.split(" ", 1)[0].strip('"') or None


def debug_port_of(joined):
    return flag_value(joined, "remote-debugging-port")


def profile_of(joined):
    return flag_value(joined, "user-data-dir")


def owned_pids():
    wanted = os.path.realpath(PROFILE)
    pids = []
    for pid, joined in browser_processes():
        current = profile_of(joined)
        if current and os.path.realpath(current) == wanted:
            pids.append(pid)
    return pids


def cmd_doctor(args):
    version = cdp_version(args.port)
    print(f"agent port   : {args.port} -> " + ("open" if version else "closed"))
    if version:
        print(f"  browser    : {version.get('Browser', 'unknown')}")
        targets = [t for t in cdp_targets(args.port) if t.get("type") == "page"]
        print(f"  pages      : {len(targets)}")
        for target in targets[:5]:
            print(f"    - {target.get('title') or '(untitled)'} :: {target.get('url')}")

    automation = cdp_version(AUTOMATION_PORT)
    if automation:
        print(f"automation   : {AUTOMATION_PORT} -> {automation.get('Browser', 'unknown')} (hidden)")

    desktop = []
    headless = []
    for pid, joined in browser_processes():
        target = (pid, debug_port_of(joined), profile_of(joined))
        if process_kind(joined) == "desktop":
            desktop.append(target)
        else:
            headless.append(target)

    for pid, port, profile in headless:
        if str(port) == str(AUTOMATION_PORT):
            continue
        print(f"headless     : pid {pid} cdp :{port or 'none'} (not visible)")

    if not desktop:
        print("desktop      : no visible Chromium browser process found")
    for pid, port, profile in desktop:
        where = profile or "(default profile)"
        state = f"cdp :{port}" if port else "no cdp port"
        print(f"desktop      : pid {pid} {state} {where}")

    print(f"agent profile: {PROFILE} " + ("(running)" if owned_pids() else "(stopped)"))
    return 0


def cmd_launch(args):
    if cdp_version(args.port):
        print(f"already running on :{args.port}")
        return 0

    flatpak = shutil.which("flatpak")
    if not flatpak:
        print("flatpak not found; cannot start the headed agent browser", file=sys.stderr)
        return 1

    os.makedirs(PROFILE, exist_ok=True)
    command = [
        flatpak,
        "run",
        FLATPAK_APP,
        f"--remote-debugging-port={args.port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        args.url or "about:blank",
    ]
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        version = cdp_version(args.port)
        if version:
            print(f"headed Chromium ready on :{args.port}")
            print(f"  browser : {version.get('Browser', 'unknown')}")
            print(f"  profile : {PROFILE}")
            return 0
        time.sleep(0.5)

    print("timed out waiting for the CDP endpoint", file=sys.stderr)
    return 1


def cmd_stop(args):
    pids = owned_pids()
    if not pids:
        print("agent browser is not running")
        return 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue
    print(f"stopped {len(pids)} agent browser process(es)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Headed Chromium CDP helper")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="report browser and port state")
    doctor.set_defaults(func=cmd_doctor)

    launch = sub.add_parser("launch", help="start the headed agent browser")
    launch.add_argument("url", nargs="?", default=None)
    launch.set_defaults(func=cmd_launch)

    stop = sub.add_parser("stop", help="stop the headed agent browser")
    stop.set_defaults(func=cmd_stop)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
