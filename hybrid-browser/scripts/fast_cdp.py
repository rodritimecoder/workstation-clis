#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.sync_api import sync_playwright

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
PID_FILE = Path("/tmp/fast_cdp_daemon.pid")

def goal_keywords(goal: str) -> List[str]:
    """Split a goal into comparable words: lowercased, alphanumeric, >= 3 chars."""
    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", goal)
    return [w.lower() for w in normalized.split() if len(w) >= 3]


def select_target(
    keywords: List[str], candidates: List[Dict[str, str]]
) -> Optional[tuple]:
    """Pick the candidate whose label covers the most of the goal's words.

    `uat` used to hand this list to a decision model. The list is already
    resolved from the DOM by the extraction script below, so that was a model
    round trip to redo a choice the caller had already made -- and it made a
    deterministic browser test depend on a multi-gigabyte server being up.
    Scoring labels locally is reproducible, needs no VRAM, and reports the
    words it matched so a wrong pick is debuggable.

    Ties break toward the earlier element in DOM order. Returns None when
    nothing matches, so the caller can ask for an explicit --ref.
    """
    if not keywords:
        return None

    best = None
    for candidate in candidates:
        ref = candidate["ref"]
        haystack = candidate["description"].lower()
        matched = [k for k in keywords if k in haystack]
        if not matched:
            continue
        # Strictly greater keeps the earlier candidate on a tie.
        if best is None or len(matched) > len(best[1]):
            best = (ref, matched)

    if best is None:
        return None

    ref, matched = best
    score = round(len(matched) / len(keywords), 3)
    return ref, matched, score


def list_candidates(candidates: List[Dict[str, str]]) -> str:
    return "\n".join(f"  {c['ref']}: {c['description']}" for c in candidates)


def find_chromium_binary() -> Optional[str]:
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if cache_dir.exists():
        shells = list(cache_dir.glob("**/chrome-headless-shell"))
        if shells and shells[0].is_file() and os.access(shells[0], os.X_OK):
            return str(shells[0])
        chromes = list(cache_dir.glob("**/chrome-linux64/chrome"))
        if chromes and chromes[0].is_file() and os.access(chromes[0], os.X_OK):
            return str(chromes[0])
    for candidate in ["chromium", "chromium-browser", "google-chrome"]:
        path = subprocess.run(["which", candidate], capture_output=True, text=True).stdout.strip()
        if path and os.access(path, os.X_OK):
            return path
    return None

def is_cdp_running(url: str = CDP_URL) -> bool:
    try:
        req = urllib.request.Request(f"{url}/json/version", headers={"User-Agent": "FastCDP"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_cdp_daemon() -> None:
    if is_cdp_running():
        return
    binary = find_chromium_binary()
    if not binary:
        raise RuntimeError("No headless chromium or chrome-headless-shell found.")
    cmd = [
        binary,
        f"--remote-debugging-port={CDP_PORT}",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--no-first-run",
        "--disable-default-apps",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    PID_FILE.write_text(str(proc.pid))
    for _ in range(30):
        time.sleep(0.05)
        if is_cdp_running():
            return
    raise TimeoutError("Failed to warm CDP daemon within 1.5 seconds.")

def stop_cdp_daemon() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            return True
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return False

class FastCDP:
    def __init__(self, cdp_url: str = CDP_URL, block_media: bool = True):
        ensure_cdp_daemon()
        self.cdp_url = cdp_url
        self.block_media = block_media
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.connect_over_cdp(self.cdp_url)

    def verify(
        self,
        url: str,
        assert_selector: Optional[str] = None,
        assert_text: Optional[str] = None,
        eval_script: Optional[str] = None,
        click_selector: Optional[str] = None,
        type_target: Optional[str] = None,
        type_text: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        context = self.browser.new_context()
        page = context.new_page()

        if self.block_media:
            cdp_session = context.new_cdp_session(page)
            cdp_session.send(
                "Network.setBlockedURLs",
                {
                    "urls": [
                        "*.png",
                        "*.jpg",
                        "*.jpeg",
                        "*.webp",
                        "*.gif",
                        "*.svg",
                        "*.woff*",
                        "*.woff2",
                        "*.ttf",
                        "*analytics*",
                        "*googletagmanager*",
                    ]
                },
            )

        passed_checks: List[str] = []
        errors: List[str] = []
        eval_result: Any = None

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = page.title()

            if click_selector:
                page.locator(click_selector).first.click(timeout=timeout_ms)
                passed_checks.append(f"click:{click_selector}")

            if type_target and type_text is not None:
                page.locator(type_target).first.fill(type_text, timeout=timeout_ms)
                passed_checks.append(f"type:{type_target}")

            if assert_selector:
                page.locator(assert_selector).first.wait_for(state="attached", timeout=timeout_ms)
                passed_checks.append(f"selector:{assert_selector}")

            if assert_text:
                found_text = page.inner_text("body", timeout=timeout_ms)
                if assert_text not in found_text:
                    raise AssertionError(f"Expected text '{assert_text}' not found in body.")
                passed_checks.append(f"text:{assert_text}")

            if eval_script:
                eval_result = page.evaluate(eval_script)
                passed_checks.append(f"eval:{eval_script}")

            if screenshot_path:
                page.screenshot(path=screenshot_path)
                passed_checks.append(f"screenshot:{screenshot_path}")

        except Exception as exc:
            errors.append(str(exc))
        finally:
            page.close()
            context.close()

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "ok": len(errors) == 0,
            "url": url,
            "title": title if "title" in locals() else "",
            "duration_ms": duration_ms,
            "passed_checks": passed_checks,
            "errors": errors,
            "eval_result": eval_result,
        }

    def uat(
        self,
        url: str,
        goal: str,
        expect_text: Optional[str] = None,
        expect_url: Optional[str] = None,
        target_ref: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        context = self.browser.new_context()
        page = context.new_page()

        if self.block_media:
            cdp_session = context.new_cdp_session(page)
            cdp_session.send(
                "Network.setBlockedURLs",
                {
                    "urls": [
                        "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.svg",
                        "*.woff*", "*.woff2", "*.ttf", "*analytics*", "*googletagmanager*"
                    ]
                },
            )

        errors: List[str] = []
        action_log: List[Dict[str, Any]] = []

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = page.title()

            extract_script = """
            (() => {
                const elements = [];
                const candidates = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])');
                let idx = 0;
                for (const el of candidates) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                        idx++;
                        const tag = el.tagName.toLowerCase();
                        const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.id || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
                        const role = el.getAttribute('role') || tag;
                        const ref = `uat-${idx}`;
                        el.setAttribute('data-uat-ref', ref);
                        elements.push({
                            ref: ref,
                            description: `${role} '${text}'`
                        });
                    }
                }
                return elements;
            })()
            """
            candidates = page.evaluate(extract_script)
            if not candidates:
                raise RuntimeError(f"No interactive elements found on page: {url}")

            # DOM order matters: ties must resolve reproducibly.
            candidates = candidates[:20]
            by_ref = {c["ref"]: c["description"] for c in candidates}

            if target_ref:
                if target_ref not in by_ref:
                    raise RuntimeError(
                        f"--ref '{target_ref}' is not on the page. Candidates:\n"
                        + list_candidates(candidates)
                    )
                selected_ref, matched_on, match_score = target_ref, [], 1.0
                how = "explicit_ref"
            else:
                picked = select_target(goal_keywords(goal), candidates)
                if picked is None:
                    raise RuntimeError(
                        f"No candidate matched the goal '{goal}'. Pass --ref to pick one of:\n"
                        + list_candidates(candidates)
                    )
                selected_ref, matched_on, match_score = picked
                how = "keyword_match"

            selected_desc = by_ref.get(selected_ref, "Unknown")

            action_log.append({
                "action": "click",
                "ref": selected_ref,
                "description": selected_desc,
                "selection": how,
                "matched_on": matched_on,
                "match_score": match_score,
            })

            page.locator(f'[data-uat-ref="{selected_ref}"]').first.click(timeout=timeout_ms)
            page.wait_for_timeout(100)

            if expect_text:
                body_text = page.inner_text("body", timeout=timeout_ms)
                if expect_text not in body_text:
                    raise AssertionError(f"Expected UAT text '{expect_text}' not found after action.")

            if expect_url:
                if expect_url not in page.url:
                    raise AssertionError(f"Expected UAT URL to contain '{expect_url}', got '{page.url}'.")

            # Without an assertion there is nothing to verify, and a model's
            # opinion of "that looks about right" is exactly the unverifiable
            # claim UAT exists to remove. Say so plainly instead.
            verification_verdict = (
                "verified_by_assertions" if (expect_text or expect_url) else "action_executed"
            )

            if screenshot_path:
                page.screenshot(path=screenshot_path)

        except Exception as exc:
            errors.append(str(exc))
        finally:
            page.close()
            context.close()

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "ok": len(errors) == 0,
            "url": url,
            "goal": goal,
            "duration_ms": duration_ms,
            "actions": action_log,
            "verification": verification_verdict if "verification_verdict" in locals() else "failed",
            "errors": errors,
        }

    def close(self) -> None:
        self.browser.close()
        self._pw.stop()

def main() -> int:
    parser = argparse.ArgumentParser(description="Ultra-fast deterministic browser verification via warm CDP daemon.")
    subparsers = parser.add_subparsers(dest="subcommand")

    daemon_parser = subparsers.add_parser("daemon")
    daemon_parser.add_argument("action", choices=["start", "stop", "status"])

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("url", help="Target URL to verify")
    verify_parser.add_argument("--assert-selector", dest="assert_selector", help="Assert element exists in DOM")
    verify_parser.add_argument("--assert-text", dest="assert_text", help="Assert text is present in body")
    verify_parser.add_argument("--eval", dest="eval_script", help="Evaluate JavaScript expression")
    verify_parser.add_argument("--click", dest="click_selector", help="Click selector prior to verification")
    verify_parser.add_argument("--type-target", dest="type_target", help="Selector to type into")
    verify_parser.add_argument("--type-text", dest="type_text", help="Text to fill into type-target")
    verify_parser.add_argument("--screenshot", dest="screenshot_path", help="Save evidence screenshot path")
    verify_parser.add_argument("--no-block-media", dest="no_block_media", action="store_true", help="Disable media/font blocking")
    verify_parser.add_argument("--timeout", type=int, default=5000, help="Operation timeout in ms")
    verify_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    uat_parser = subparsers.add_parser("uat", help="Deterministic UAT driving: match the goal to an element and assert the result.")
    uat_parser.add_argument("url", help="Target URL to test")
    uat_parser.add_argument("--goal", required=True, help="UAT goal (e.g. 'Click checkout button')")
    uat_parser.add_argument("--expect-text", dest="expect_text", help="Assert text appears after action")
    uat_parser.add_argument("--expect-url", dest="expect_url", help="Assert URL changes after action")
    uat_parser.add_argument("--ref", dest="target_ref", help="Act on this exact candidate ref instead of matching the goal")
    uat_parser.add_argument("--screenshot", dest="screenshot_path", help="Save evidence screenshot path")
    uat_parser.add_argument("--no-block-media", dest="no_block_media", action="store_true", help="Disable media/font blocking")
    uat_parser.add_argument("--timeout", type=int, default=5000, help="Operation timeout in ms")
    uat_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.subcommand == "daemon":
        if args.action == "start":
            ensure_cdp_daemon()
            print(json.dumps({"status": "running", "cdp_url": CDP_URL}))
            return 0
        elif args.action == "stop":
            stopped = stop_cdp_daemon()
            print(json.dumps({"status": "stopped" if stopped else "not_running"}))
            return 0
        elif args.action == "status":
            running = is_cdp_running()
            print(json.dumps({"status": "running" if running else "stopped", "cdp_url": CDP_URL}))
            return 0 if running else 1

    elif args.subcommand == "verify":
        client = FastCDP(block_media=not args.no_block_media)
        try:
            result = client.verify(
                url=args.url,
                assert_selector=args.assert_selector,
                assert_text=args.assert_text,
                eval_script=args.eval_script,
                click_selector=args.click_selector,
                type_target=args.type_target,
                type_text=args.type_text,
                screenshot_path=args.screenshot_path,
                timeout_ms=args.timeout,
            )
        finally:
            client.close()

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status = "PASS" if result["ok"] else "FAIL"
            print(f"[{status}] {result['url']} ({result['duration_ms']}ms) - Checks: {len(result['passed_checks'])}")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  Error: {err}", file=sys.stderr)
        return 0 if result["ok"] else 1

    elif args.subcommand == "uat":
        client = FastCDP(block_media=not args.no_block_media)
        try:
            result = client.uat(
                url=args.url,
                goal=args.goal,
                expect_text=args.expect_text,
                expect_url=args.expect_url,
                target_ref=args.target_ref,
                screenshot_path=args.screenshot_path,
                timeout_ms=args.timeout,
            )
        finally:
            client.close()

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status = "PASS" if result["ok"] else "FAIL"
            chosen = result["actions"][0] if result["actions"] else {}
            print(f"[{status}] UAT Goal: '{result['goal']}' ({result['duration_ms']}ms)")
            if chosen:
                print(
                    f"  Target: {chosen.get('ref')} ({chosen.get('description')}) "
                    f"- {chosen.get('selection')} score={chosen.get('match_score')}"
                )
            print(f"  Verdict: {result['verification']}")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  Error: {err}", file=sys.stderr)
        return 0 if result["ok"] else 1

    parser.print_help()
    return 1

if __name__ == "__main__":
    sys.exit(main())
