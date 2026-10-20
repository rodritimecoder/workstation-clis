---
name: hybrid-browser

description: >
  Drive a sandboxed Chromium over CDP: navigate, click, type, screenshot, and
  verify pages. Selector-driven by default; an opt-in local vision fallback
  handles canvas, SVG and closed Shadow DOM targets that have no selector.

license: "Proprietary. Complete terms are in the LICENSE file at the repository root."
compatibility: "Requires the Podman container runtime and a Chromium browser; drives Chrome DevTools Protocol on :9222."
metadata:
  author: "rodri"
allowed-tools: "Bash(hybrid-browser:*) Bash(podman:*) Bash(python3:*) Read Write"
---

# Hybrid Browser (`hybrid-browser`)

A tiered web automation skill for local agent workloads. A native Rust CDP
client (`playwright-rs`, ~3ms cold start) drives a sandboxed Chromium over
DevTools Protocol.

Clicks are selector-driven by default. When the DOM yields nothing — `<canvas>`,
SVG dashboards, closed Shadow DOM, text baked into images — a Python wrapper can
fall back to `DeskForge-Qwen3.5-4B` on `:8088`, but that path is **opt-in and off
by default**: `:8088` is archived, and a locator beats a coordinate guess
wherever a selector exists. Enable it with `HYBRID_BROWSER_VISION=1` and
the archived `deskforge-qwen.sh` launcher (`sh/archived/` on the AI volume).

---

## 🏛️ The Three Paths

| Path | Use it when | Command | Example question |
| :--- | :--- | :--- | :--- |
| **Native CDP** | The DOM yields a selector | `playwright-rs` | *"Click the login button"* |
| **Vision fallback** (opt-in) | The element has no selector at all — canvas/closed Shadow DOM only | `HYBRID_BROWSER_VISION=1 hybrid-browser --click` | *"Click the blue submit button in the chart"* |
| **Deterministic verify** | You need a pass or fail, not a session | `fast-cdp verify` | *"Is the Dashboard heading rendered?"* |
| **Goal-directed UAT** | You want to drive a flow and assert the outcome | `fast-cdp uat` | *"Proceed to checkout, then check for 'Checkout Successful'"* |

`uat` picks its target deterministically: it extracts the interactive elements
from the DOM, scores each label against the goal's words, and clicks the best
match. It reports `selection` (`explicit_ref` or `keyword_match`), `matched_on`
and `match_score`, so a wrong pick is debuggable rather than mysterious. When
nothing matches it fails with the candidate list instead of clicking blindly.

This path deliberately uses **no model**. The candidate list is already resolved
from the DOM, so sending it to a model would be a round trip to redo the
caller's own decision — and it would make a deterministic browser test depend
on an inference server being up. Only the selector-less vision fallback, above,
calls a model (`DeskForge`, `:8088`).

Verdicts come from assertions. Without `--expect-text` or `--expect-url` the
result is reported as `action_executed`, not as verified.

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

# 10. Goal-directed UAT — the goal's words pick the element
fast-cdp uat "http://localhost:3000" --goal "Proceed to checkout" --expect-text "Checkout Successful"

# 11. ...or name the element yourself, when labels are ambiguous
fast-cdp uat "http://localhost:3000" --ref uat-2 --expect-text "Checkout Successful"

# 12. Close the session
playwright-rs close
```

---

## Reference

- `references/architecture.md` — tiers, ports (:3010, :9222, :8088), profile path
