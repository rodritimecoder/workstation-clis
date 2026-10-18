---
name: hybrid-browser
description: "Tiered browser automation agent using Podman Chromium, Chrome DevTools Protocol (CDP), and DeskForge-Qwen3.5-4B visual grounding fallback. Use whenever asked to browse the web, interact with authenticated web portals, click complex canvas/SVG buttons, or automate web flows."
---

# Hybrid Browser (Playwright + DeskForge Grounding)

A tiered web automation skill designed for local LLM workloads. It automates a sandboxed Chromium instance running inside Podman, splitting tasks across two tiers:
1. **Tier 1 (Fast Path):** Uses native Playwright accessibility & DOM locators over Chrome DevTools Protocol (`:9222`) for instant, token-free clicks.
2. **Tier 2 (Vision Fallback):** When elements are drawn on `<canvas>`, SVG dashboards, Shadow DOM, or obfuscated React widgets, it takes a screenshot, resizes via Lanczos even-dimensions, and queries local `DeskForge-Qwen3.5-4B` (`:8088`) for normalized `(x, y)` coordinates to click.

---

## Architecture & Ports

| Component | Endpoint | Purpose |
| :--- | :--- | :--- |
| **Podman Container (`hybrid-browser`)** | `http://127.0.0.1:3010` | Live interactive KasmVNC web desktop (you can watch or log in manually) |
| **Chromium CDP** | `http://127.0.0.1:9222` | Direct Chrome DevTools Protocol automated by Playwright |
| **DeskForge Server** | `http://127.0.0.1:8088` | Local `DeskForge-Qwen3.5-4B` running on Vulkan dual RX 9060 XT |

Persistent profile directory is preserved across container restarts at:
`~/.local/share/hybrid-browser-profile`

---

## Quick Start Commands

### 1. Start the Background Services
Starts the rootless Podman browser container and warms up DeskForge on port 8088:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/service.sh start
```

### 2. View the Live Interactive GUI (KasmVNC)
Opens the live browser screen in a borderless native app window:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/service.sh gui
```
*(Or navigate to `http://127.0.0.1:3010` in any web browser).*

### 3. Check Service Status
```bash
~/.gemini/config/skills/hybrid-browser/scripts/service.sh status
```

### 4. Stop All Services
```bash
~/.gemini/config/skills/hybrid-browser/scripts/service.sh stop
```

---

## Driving the Browser via CLI

Use the python wrapper `run.sh` to drive navigation and interactions:

### Navigate to a page:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --url "https://news.ycombinator.com"
```

### Click an element (attempts DOM first, falls back to DeskForge vision):
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --click "login"
```

### Type into the focused input field:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --type "myusername"
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --press "Tab"
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --type "mypassword"
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --press "Enter"
```

### Get a clean text snapshot of the current viewport:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --snapshot
```

### Capture screenshot to file:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --screenshot "/tmp/current_page.png"
```

### Interactive REPL Mode:
```bash
~/.gemini/config/skills/hybrid-browser/scripts/run.sh --interactive
```
In the REPL:
- `goto <url>`
- `click <button text or visual description>`
- `type <text>`
- `press <key>`
- `snap`
- `screenshot`

---

## Ultra-Fast Native Playwright CLI & CDP Verification (`playwright-rs` / `fast-cdp`)

`hybrid-browser` includes a compiled native Rust binary (`fast-cdp-rs`, aliased as `playwright-rs` and `fast-cdp`) communicating directly over Chrome DevTools Protocol (`:9222`) WebSockets. It replaces heavyweight Node.js Playwright CLI runs (3ms cold start vs 183ms, 3ms snapshot vs 470ms).

### 1. Interactive Session Commands (`playwright-rs`)

For stateful interactive browser navigation, DOM inspection, and form interactions across multiple CLI calls:

```bash
# Open a URL (starts background headless engine or connects to :9222)
playwright-rs open "https://example.com"

# Capture accessibility snapshot with numbered ref IDs (3ms)
playwright-rs snapshot

# Click an element by its ref ID (e.g. e1) or CSS selector
playwright-rs click e1

# Fill or type into form inputs
playwright-rs fill e2 "search query"
playwright-rs press Enter

# Run JavaScript in the page context
playwright-rs eval "document.title"

# Capture a PNG screenshot
playwright-rs screenshot /tmp/result.png

# Cleanly close the session
playwright-rs close
```

### 2. Multi-Session & Container Attachment

```bash
# Work in a specific named session:
playwright-rs -s work open "https://github.com"
playwright-rs -s work snapshot

# Attach directly to the running hybrid-browser Podman container (:9222 / KasmVNC :3010):
playwright-rs attach --cdp "http://127.0.0.1:9222"
```

### 3. One-Shot Deterministic Verification (`fast-cdp verify`)

```bash
# Verify selector & text presence in <40ms
fast-cdp verify "http://localhost:3000" \
  --assert-selector "h1" \
  --assert-text "Dashboard" \
  --json

# Click and verify dynamic state update
fast-cdp verify "http://localhost:3000" \
  --click "#submit-btn" \
  --assert-text "Saved successfully" \
  --screenshot "/tmp/verification_proof.png"
```

### 4. Autonomous UAT Mode (Jev / JPT-4B Driven)

Autonomous goal-directed browser actions in 200–400ms without Vision model overhead:
```bash
# Hand interactive elements to JPT-4B (:8090) to decide and click the checkout button:
fast-cdp uat "http://localhost:3000" \
  --goal "Proceed to checkout" \
  --expect-text "Checkout Successful" \
  --model jpt \
  --json
```


