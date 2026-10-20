#!/usr/bin/env python3
"""
Hybrid Browser Engine: Playwright (DOM Fast-Path) + optional DeskForge vision fallback.

Talks to Chromium over CDP (:9222). The DeskForge-Qwen3.5-4B fallback (:8088) is
archived and opt-in via HYBRID_BROWSER_VISION=1; selectors are the default.
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path


def _reexec_in_venv() -> None:
    """Re-exec under the skill venv when Playwright is missing.

    Playwright lives in the skill's virtualenv, not the system interpreter, and
    bundle copies are rsynced with `--exclude .venv` -- so look in both places
    before giving up. Guarded by an env var so the hop happens only once.
    """
    try:
        import playwright  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("_HYBRID_BROWSER_VENV_REEXEC") == "1":
        return
    here = Path(__file__).resolve()
    skill_dir = here.parent.parent
    candidates = (
        skill_dir / ".venv" / "bin" / "python",
        Path.home() / ".venvs" / skill_dir.name / "bin" / "python",
    )
    venv_py = next((c for c in candidates if c.is_file()), None)
    if venv_py is None:
        return
    try:
        if venv_py.resolve() == Path(sys.executable).resolve():
            return
    except OSError:
        return
    env = dict(os.environ, _HYBRID_BROWSER_VENV_REEXEC="1")
    os.execve(str(venv_py), [str(venv_py), str(here), *sys.argv[1:]], env)


_reexec_in_venv()

from PIL import Image  # noqa: E402
import requests  # noqa: E402
from playwright.sync_api import (  # noqa: E402
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

DESKFORGE_URL = "http://127.0.0.1:8088/v1/chat/completions"

# :8088 is archived, so the vision tier is kept but off by default. Wherever the
# DOM yields a selector, a locator beats a coordinate guess: exact text, single-
# digit milliseconds, no 4 GB model resident and no sampling. The fallback only
# earns its keep on <canvas>/WebGL, closed shadow roots and text baked into
# images -- so it has to be asked for explicitly.
VISION_FALLBACK = os.environ.get("HYBRID_BROWSER_VISION", "").strip().lower() in (
    "1", "true", "yes", "on",
)
CDP_URL = "http://127.0.0.1:9222"

SYSTEM_PROMPT = """You are a computer-use agent operating a desktop graphical interface. At each step you see the user's task, a screenshot of the current screen, and the actions you have already taken. Reply with the next action as pyautogui code and nothing else -- no explanation, no code fence, no commentary.

Coordinates are fractions of the screen, not pixels: x runs from 0.0 at the left edge to 1.0 at the right edge, y from 0.0 at the top to 1.0 at the bottom. Write both with four decimals.

These are the only actions available:
pyautogui.click(x=0.0000, y=0.0000)
pyautogui.doubleClick(x=0.0000, y=0.0000)
pyautogui.rightClick(x=0.0000, y=0.0000)
pyautogui.middleClick(x=0.0000, y=0.0000)
computer.tripleClick(x=0.0000, y=0.0000)
pyautogui.moveTo(x=0.0000, y=0.0000)
pyautogui.dragTo(x=0.0000, y=0.0000, button='left')
pyautogui.scroll(-4)
pyautogui.hscroll(4)
pyautogui.write(message='text to type')
pyautogui.press('enter')
pyautogui.hotkey(['ctrl', 'c'])
computer.wait()
computer.terminate(status='success')

To scroll at a particular place, move there first and then scroll. When the task is finished, or cannot be finished, end with computer.terminate."""

def fit_lanczos_even(image: Image.Image, max_pixels: int = 2_097_152) -> Image.Image:
    """Official Hugging Face DeskForge preprocessing: Lanczos downscale with even dimensions."""
    w, h = image.size
    if w * h <= max_pixels:
        return image
    s = (max_pixels / (w * h)) ** 0.5
    new_w = max(2, int(w * s) // 2 * 2)
    new_h = max(2, int(h * s) // 2 * 2)
    return image.resize((new_w, new_h), Image.LANCZOS)

def parse_deskforge_action(action_text: str):
    """Extract coordinates and action type from DeskForge pyautogui response."""
    cleaned = re.sub(r"<think>.*?</think>", "", action_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"<\|channel>thought.*?<channel\|>", "", cleaned, flags=re.DOTALL).strip()
    
    coord_match = re.search(r"x=([\d.]+),\s*y=([\d.]+)", cleaned)
    coords = None
    if coord_match:
        coords = (float(coord_match.group(1)), float(coord_match.group(2)))
        
    return {
        "raw": action_text,
        "clean": cleaned,
        "coords": coords,
        "is_click": "click" in cleaned.lower(),
        "is_type": "write" in cleaned.lower(),
        "is_terminate": "terminate" in cleaned.lower()
    }

class HybridBrowser:
    def __init__(self, cdp_url=CDP_URL):
        self.cdp_url = cdp_url
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
        except Exception as e:
            print(f"[Error] Failed to connect to Chromium at {self.cdp_url}: {e}")
            print("Make sure the Podman container is running via: hybrid-browser-service.sh start")
            sys.exit(1)
            
        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        overlay_file = Path(__file__).parent / "cursor_overlay.js"
        if overlay_file.is_file():
            self.context.add_init_script(path=str(overlay_file))
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def navigate(self, url: str):
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        print(f"[*] Navigating to: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(1000)
        return self.page.title()

    def click(self, target_description: str) -> bool:
        """
        Tiered Execution:
        1. Fast Path: Playwright DOM locator by text / role / placeholder / label.
        2. Hard Path: DeskForge Vision Grounding on failure.
        """
        print(f"\n[Action] Requesting click on: '{target_description}'")

        # --- TIER 1: FAST PATH (Playwright DOM) ---
        print("  -> [Tier 1: DOM Fast-Path] Checking accessibility tree & locators...")
        try:
            locators = [
                self.page.get_by_role("button", name=target_description, exact=False),
                self.page.get_by_role("link", name=target_description, exact=False),
                self.page.get_by_text(target_description, exact=False),
                self.page.get_by_label(target_description, exact=False),
                self.page.get_by_placeholder(target_description, exact=False),
            ]
            for loc in locators:
                if loc.count() > 0 and loc.first.is_visible():
                    box = loc.first.bounding_box()
                    if box:
                        target_x = box["x"] + box["width"] / 2
                        target_y = box["y"] + box["height"] / 2
                        self._glide_cursor(target_x, target_y)
                    loc.first.click(timeout=2000)
                    print(f"  [✓ DOM Success] Clicked '{target_description}' natively (0 VLM tokens).")
                    self.page.wait_for_timeout(1000)
                    self.page.evaluate("window.__hideAgentCursor?.()")
                    return True
        except Exception as e:
            print(f"  [DOM Skipped] {e}")

    def _glide_cursor(self, target_x: float, target_y: float, steps: int = 25):
        try:
            current = self.page.evaluate("() => ({ x: parseFloat(document.getElementById('agent-cursor-overlay')?.style.left || 0), y: parseFloat(document.getElementById('agent-cursor-overlay')?.style.top || 0) })")
            start_x = current.get("x", target_x)
            start_y = current.get("y", target_y)
            if start_x <= 0:
                start_x, start_y = target_x, target_y

            for i in range(1, steps + 1):
                t = i / steps
                cx = start_x + (target_x - start_x) * t
                cy = start_y + (target_y - start_y) * t
                self.page.evaluate(f"window.__moveAgentCursor?.({cx:.1f}, {cy:.1f})")
                time.sleep(0.01)
            self.page.evaluate(f"window.__agentClick?.({target_x:.1f}, {target_y:.1f})")
            self.page.mouse.move(target_x, target_y)
        except Exception:
            pass

        # --- TIER 2: HARD PATH (DeskForge Vision Grounding) ---
        if not VISION_FALLBACK:
            print("  [✗ No DOM match] Vision fallback is off (:8088 is archived).")
            print("      Enable it only for canvas/closed-shadow targets: "
                  "HYBRID_BROWSER_VISION=1 plus the archived deskforge-qwen.sh launcher.")
            return False
        print(f"  -> [Tier 2: DeskForge Vision Fallback] Element obscured/canvas/custom. Capturing screenshot...")
        return self._deskforge_click(target_description)

    def _deskforge_click(self, instruction: str) -> bool:
        screenshot_bytes = self.page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        orig_w, orig_h = img.size

        fitted = fit_lanczos_even(img)
        buf = io.BytesIO()
        fitted.save(buf, format="PNG")
        b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
                        {"type": "text", "text": f"Task: Click on {instruction}\n\nActions already taken:\n(none -- this is the first step)\n\nNext action:"}
                    ]
                }
            ],
            "max_tokens": 64,
            "temperature": 0.0,
            # Raw requests.post, not the OpenAI SDK, so this is the literal
            # body key llama-server reads. "extra_body" only exists in the SDK
            # and would be ignored here, leaving Qwen3.5 to spend the 64-token
            # budget on reasoning_content and return empty content.
            "chat_template_kwargs": {"enable_thinking": False}
        }

        t0 = time.time()
        try:
            res = requests.post(DESKFORGE_URL, json=payload, timeout=30)
            elapsed = time.time() - t0
        except Exception as e:
            print(f"  [✗ DeskForge Error] Could not reach server at {DESKFORGE_URL}: {e}")
            return False

        if res.status_code != 200:
            print(f"  [✗ DeskForge Error] Status {res.status_code}: {res.text}")
            return False

        action_data = parse_deskforge_action(res.json()["choices"][0]["message"]["content"])
        print(f"  [DeskForge VLM ({elapsed:.2f}s)]: {action_data['clean']}")

        if action_data["coords"]:
            nx, ny = action_data["coords"]
            pixel_x = round(nx * orig_w)
            pixel_y = round(ny * orig_h)
            self._glide_cursor(pixel_x, pixel_y, steps=30)
            self.page.mouse.click(pixel_x, pixel_y)
            self.page.wait_for_timeout(1000)
            self.page.evaluate("window.__hideAgentCursor?.()")
            return True
        else:
            print(f"  [✗ Failed] DeskForge did not return valid click coordinates.")
            return False

    def type_text(self, text: str):
        print(f"[*] Typing text: '{text}'")
        self.page.keyboard.type(text)
        self.page.wait_for_timeout(500)

    def press_key(self, key: str):
        print(f"[*] Pressing key: '{key}'")
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(500)

    def snapshot_text(self) -> str:
        """Lightweight text representation of visible page."""
        title = self.page.title()
        url = self.page.url
        body_text = self.page.inner_text("body")
        # Truncate to first 2000 chars for clean LLM context
        truncated = body_text[:2000] if len(body_text) > 2000 else body_text
        return f"Title: {title}\nURL: {url}\n\nVisible Text:\n{truncated}"

    def screenshot_save(self, output_path: str = "/tmp/browser_view.png"):
        self.page.screenshot(path=output_path)
        print(f"[✓] Screenshot saved to: {output_path}")
        return output_path

    def close(self):
        self.browser.close()
        self.playwright.stop()

def main():
    parser = argparse.ArgumentParser(description="Hybrid Playwright + DeskForge Browser CLI")
    parser.add_argument("--url", help="URL to navigate to")
    parser.add_argument("--click", help="Element text or description to click")
    parser.add_argument("--type", help="Text to type into focused field")
    parser.add_argument("--press", help="Key to press (e.g. Enter, Tab, Escape)")
    parser.add_argument("--snapshot", action="store_true", help="Print visible text snapshot")
    parser.add_argument("--screenshot", help="Capture screenshot to file path")
    parser.add_argument("--interactive", action="store_true", help="Interactive REPL mode")

    args = parser.parse_args()

    browser = HybridBrowser()

    if args.url:
        browser.navigate(args.url)
    if args.click:
        browser.click(args.click)
    if args.type:
        browser.type_text(args.type)
    if args.press:
        browser.press_key(args.press)
    if args.snapshot:
        print("\n=== Page Snapshot ===")
        print(browser.snapshot_text())
    if args.screenshot:
        browser.screenshot_save(args.screenshot)

    if args.interactive:
        print("\n=== Hybrid Browser Interactive Shell ===")
        print("Commands: goto <url> | click <text> | type <text> | press <key> | snap | screenshot | exit")
        while True:
            try:
                cmd = input("\nhybrid-browser> ").strip()
                if not cmd or cmd == "exit":
                    break
                parts = cmd.split(" ", 1)
                action = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if action in ["goto", "nav", "url"]:
                    browser.navigate(arg)
                elif action == "click":
                    browser.click(arg)
                elif action == "type":
                    browser.type_text(arg)
                elif action == "press":
                    browser.press_key(arg)
                elif action == "snap":
                    print(browser.snapshot_text())
                elif action == "screenshot":
                    path = arg or "/tmp/browser_view.png"
                    browser.screenshot_save(path)
                else:
                    print(f"Unknown command: {action}")
            except (KeyboardInterrupt, EOFError):
                break

    browser.close()

if __name__ == "__main__":
    main()
