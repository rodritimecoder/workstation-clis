#!/usr/bin/env python3
"""The visible-browser helper must tell a headed browser from a hidden shell.

Every case here is a cmdline shape measured on a real machine: Chromium rewrites
its own argv, so child processes arrive as one run-together string rather than
clean tokens. Classification that assumes clean tokens reports dozens of
"desktop browsers" for a single window, or none at all.
"""

import importlib.util
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "multimodal" / "playwright" / "scripts" / "desktop_cdp.py"

spec = importlib.util.spec_from_file_location("desktop_cdp", SCRIPT)
desktop_cdp = importlib.util.module_from_spec(spec)
sys.modules["desktop_cdp"] = desktop_cdp
spec.loader.exec_module(desktop_cdp)

HEADLESS_RENDERER = (
    "/home/rodri/.cache/ms-playwright/chromium_headless_shell-1243/"
    "chrome-headless-shell-linux64/chrome-headless-shell --type=renderer --headless=old "
    "--no-sandbox --remote-debugging-port=9222 --ozone-platform=headless"
)
HEADLESS_MAIN = "/home/rodri/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell --no-sandbox --headless=new --remote-debugging-port=9222"
CRASHPAD = "/app/chromium/chrome_crashpad_handler --monitor-self --database=/home/rodri/.var/app/org.chromium.Chromium/config/chromium/Crash Reports"
ZYGOTE = "/app/chromium/chrome --type=zygote --no-zygote-sandbox --crashpad-handler-pid=10"
WRAPPER = "bwrap --args 77 -- /app/bin/chromium"
DESKTOP = "/app/chromium/chrome --enable-features=WebRTCPipeWireCapturer --disable-features=WebAssemblyTrapHandler"
AGENT = f"/app/chromium/chrome --remote-debugging-port=9224 --remote-allow-origins=* --user-data-dir={desktop_cdp.PROFILE} --start-maximized"


class TestClassification(unittest.TestCase):
    def test_hidden_shell_is_never_a_desktop_window(self):
        self.assertEqual(desktop_cdp.process_kind(HEADLESS_MAIN), "headless")
        self.assertEqual(desktop_cdp.process_kind(HEADLESS_RENDERER), "child")

    def test_children_helpers_and_wrappers_are_not_browsers(self):
        for cmdline in (HEADLESS_RENDERER, CRASHPAD, ZYGOTE, WRAPPER):
            with self.subTest(cmdline=cmdline[:40]):
                self.assertNotIn(desktop_cdp.process_kind(cmdline), ("headless", "desktop"))

    def test_headed_browser_is_a_desktop_window(self):
        self.assertEqual(desktop_cdp.process_kind(DESKTOP), "desktop")
        self.assertEqual(desktop_cdp.process_kind(AGENT), "desktop")

    def test_unrelated_process_is_ignored(self):
        self.assertEqual(desktop_cdp.process_kind("/usr/bin/python3 chrome_scraper.py"), "other")


class TestFlagParsing(unittest.TestCase):
    def test_port_survives_a_run_together_cmdline(self):
        self.assertEqual(desktop_cdp.debug_port_of(HEADLESS_RENDERER), "9222")
        self.assertEqual(desktop_cdp.debug_port_of(AGENT), "9224")

    def test_missing_flags_read_as_none(self):
        self.assertIsNone(desktop_cdp.debug_port_of(DESKTOP))
        self.assertIsNone(desktop_cdp.profile_of(DESKTOP))

    def test_profile_is_recovered_exactly(self):
        self.assertEqual(desktop_cdp.profile_of(AGENT), desktop_cdp.PROFILE)


class TestProbe(unittest.TestCase):
    def test_closed_port_reports_nothing_instead_of_raising(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.assertIsNone(desktop_cdp.cdp_version(port, timeout=0.3))
        self.assertEqual(desktop_cdp.cdp_targets(port, timeout=0.3), [])

    def test_agent_port_is_distinct_from_the_automation_shell(self):
        self.assertNotEqual(desktop_cdp.DEFAULT_PORT, desktop_cdp.AUTOMATION_PORT)


if __name__ == "__main__":
    unittest.main()
