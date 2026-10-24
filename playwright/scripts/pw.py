#!/home/rodri/.venvs/playwright/bin/python3
"""Playwright-based browser helper for agent verification."""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def _browser(pw, headed=False):
    return pw.chromium.launch(headless=not headed)


def cmd_open(args):
    with sync_playwright() as pw:
        browser = _browser(pw, args.headed)
        page = browser.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        print(f"title: {page.title()}")
        print(f"url: {page.url}")
        browser.close()
    return 0


def cmd_screenshot(args):
    with sync_playwright() as pw:
        browser = _browser(pw, args.headed)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        page.screenshot(path=args.out, full_page=args.full_page)
        print(f"saved: {args.out}")
        browser.close()
    return 0


def cmd_eval(args):
    with sync_playwright() as pw:
        browser = _browser(pw, args.headed)
        page = browser.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        result = page.evaluate(args.js)
        print(result if result is not None else "")
        browser.close()
    return 0


def cmd_text(args):
    with sync_playwright() as pw:
        browser = _browser(pw, args.headed)
        page = browser.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        if args.selector:
            loc = page.locator(args.selector)
            print(loc.inner_text(timeout=args.timeout))
        else:
            print(page.inner_text("body"))
        browser.close()
    return 0


def cmd_check(args):
    with sync_playwright() as pw:
        browser = _browser(pw, args.headed)
        page = browser.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        content = page.content()
        if args.selector:
            try:
                loc_text = page.locator(args.selector).inner_text(timeout=args.timeout)
            except Exception:
                loc_text = ""
            haystack = loc_text
        else:
            haystack = content
        ok = args.text in haystack
        print(f"{'PASS' if ok else 'FAIL'}: {args.text!r} {'found' if ok else 'not found'}")
        browser.close()
        return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="Playwright browser helper")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=30000)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="Open a URL and print title/url")
    p_open.add_argument("url")
    p_open.set_defaults(func=cmd_open)

    p_ss = sub.add_parser("screenshot", help="Screenshot a URL")
    p_ss.add_argument("url")
    p_ss.add_argument("out")
    p_ss.add_argument("--width", type=int, default=1280)
    p_ss.add_argument("--height", type=int, default=720)
    p_ss.add_argument("--full-page", action="store_true", dest="full_page")
    p_ss.set_defaults(func=cmd_screenshot)

    p_eval = sub.add_parser("eval", help="Evaluate JS on a page")
    p_eval.add_argument("url")
    p_eval.add_argument("js")
    p_eval.set_defaults(func=cmd_eval)

    p_text = sub.add_parser("text", help="Get text content")
    p_text.add_argument("url")
    p_text.add_argument("--selector", default=None)
    p_text.set_defaults(func=cmd_text)

    p_check = sub.add_parser("check", help="Assert text present on page")
    p_check.add_argument("url")
    p_check.add_argument("--text", required=True)
    p_check.add_argument("--selector", default=None)
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
PY
chmod +x /home/rodri/src/my-agent-skills/multimodal/playwright/scripts/pw.py