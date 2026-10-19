---
name: hybrid-browser
description: >
  Drive a sandboxed Chromium over CDP: navigate, click, type, screenshot, and
  verify pages. Falls back to local vision grounding for canvas, SVG and
  Shadow DOM elements that have no selector.
---

# Hybrid Browser (`hybrid-browser`)

A tiered web automation skill for local agent workloads. A native Rust CDP
client (`playwright-rs`, ~3ms cold start) drives a sandboxed Chromium over
DevTools Protocol; when an element has no selector — `<canvas>`, SVG
dashboards, Shadow DOM, obfuscated React — a Python wrapper falls back to
the local `DeskForge-Qwen3.5-4B` model on `:8088` to ground the click.

---

## 🏛️ The Three Paths

| Path | Use it when | Command | Example question |
| :--- | :--- | :--- | :--- |
| **Native CDP** | The DOM yields a selector | `playwright-rs` | *"Click the login button"* |
| **Vision fallback** | The element has no selector | `hybrid-browser --click` | *"Click the blue submit button in the chart"* |
| **Deterministic verify** | You need a pass or fail, not a session | `fast-cdp verify` | *"Is the Dashboard heading rendered?"* |

---

## 🛠️ CLI Quickstart

```bash
HB="/run/media/rodri/AI/skills/hybrid-browser/scripts"

# 1. Start the browser services (Podman container + DeskForge)
python3 $HB/service.sh start

# 2. Open a URL — starts a headless engine if none is running
playwright-rs open "https://example.com"

# 3. Snapshot the page — accessibility tree with numbered ref IDs
playwright-rs snapshot

# 4. Click by ref ID, or by CSS selector
playwright-rs click e1

# 5. Fill a field and submit
playwright-rs fill e2 "search query" && playwright-rs press Enter

# 6. Run JavaScript in the page
playwright-rs eval "document.title"

# 7. Screenshot
playwright-rs screenshot /tmp/result.png

# 8. Vision-grounded click, for elements with no selector
python3 $HB/run.sh --click "login"

# 9. Verify a page in one shot — selector and text, under 40ms
fast-cdp verify "http://localhost:3000" --assert-selector "h1" --assert-text "Dashboard"

# 10. Goal-directed UAT — a model decides which element to click
fast-cdp uat "http://localhost:3000" --goal "Proceed to checkout" --expect-text "Checkout Successful"

# 11. Close the session
playwright-rs close
```

---

## Reference

- `references/architecture.md` — tiers, ports (:3010, :9222, :8088), profile path
