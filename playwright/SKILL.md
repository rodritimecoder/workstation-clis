---
name: playwright
description: >
  High-performance browser automation, DOM snapshotting, and grounded verification powered by
  native Rust (playwright-rs / fast-cdp). Direct sub-millisecond CDP execution for navigation,
  clicking, typing, accessibility tree snapshots, screenshots, JS evaluation, and automated UAT assertions.
compatibility: "Needs a Chromium CDP endpoint: the headless shell on :9222 for unattended work, or a headed Chromium on :9224 when a person must see and drive the page. Standalone native Rust binary."
allowed-tools: "Bash(playwright-rs:*) Bash(fast-cdp:*) Bash(python3:*) Bash(npx:*) Read Write"
---

# Playwright Browser (`playwright`)

> **Blazing-fast browser automation engine powered by native Rust (`playwright-rs` / `fast-cdp`).**  
> Direct sub-millisecond CDP execution over WebSocket, zero-overhead DOM snapshotting, and grounded UAT verification.

---

## ⚡ Why Rust for Browser Automation?

* **Sub-Millisecond Startup**: Single compiled static binary (`playwright-rs`). No Python virtual environment startup, no Node.js runtime initialization.
* **Direct CDP WebSocket**: Talks directly to Chromium's `:9222` debug socket using raw native WebSockets (`tungstenite`), bypassing driver abstraction layers.
* **Zero Token Bloat**: Commands return compact JSON or one-line status receipts directly to stdout.

---

## 🛠️ CLI Quickstart (Native Rust Engine)

The Rust binary is installed globally on your path as **`playwright-rs`** (and aliased as **`fast-cdp`**):

```bash
# 1. Start browser daemon or connect to running Chrome (:9222)
playwright-rs daemon start

# 2. Open or navigate to a URL (instant)
playwright-rs open "http://localhost:3000"
playwright-rs goto "http://localhost:3000/dashboard"

# 3. Snapshot accessibility tree & interactive elements (gives ref ids like e1, e2)
playwright-rs snapshot
playwright-rs snap "http://localhost:3000" --json

# 4. Interact deterministically using element refs or selectors
playwright-rs click e1
playwright-rs fill e2 "admin@example.com"
playwright-rs type "password123"
playwright-rs press Enter

# 5. Evaluate JavaScript directly in page context
playwright-rs eval "document.title"
playwright-rs eval "window.location.pathname"

# 6. Capture full-page or viewport screenshot
playwright-rs screenshot "http://localhost:3000" /tmp/screen.png

# 7. One-shot verification assertion (exits 0 on pass, 1 on fail)
playwright-rs verify "http://localhost:3000" --assert-text "Dashboard Overview"

# 8. Close session
playwright-rs close
```

---

## 👁️ A Browser the User Can Actually See (port 9224)

`:9222` is often owned by Playwright's **headless shell**, which answers CDP
perfectly and renders into nothing. Driving it looks like success from the agent
side and like a missing window from the user side — the classic "I don't see the
browser you're looking at". Slack or a session you must hand to a person needs a
headed Chromium on the desktop, with its own debug port.

`scripts/desktop_cdp.py` owns exactly that: a *headed* Chromium on port **9224**
with a separate profile, so it never collides with the user's daily browser or
with the automation shell.

```bash
# Who owns which port, and is the visible one real?
python3 scripts/desktop_cdp.py doctor
# agent port   : 9224 -> open
#   browser    : Chrome/154.0.8037.92
# automation   : 9222 -> HeadlessChrome/153 (hidden)
# desktop      : pid 7113 no cdp port (default profile)
# desktop      : pid 712232 cdp :9224 /home/rodri/.local/share/chromium-agent

# Start it on a page the user must sign in to themselves
python3 scripts/desktop_cdp.py launch "https://example.com/account"

# Drive that visible window: the port flag is the whole trick
playwright-rs -s desktop --port 9224 snapshot --json
playwright-rs -s desktop --port 9224 click e4 --expect-text "Signed in"

# Stop only the agent's own instance, matched by profile path
python3 scripts/desktop_cdp.py stop
```

Rules that keep this honest:

* **`doctor` before claiming the user can see anything.** `cdp :9224` plus a
  `desktop` line naming the agent profile is the evidence; "the snapshot returned
  elements" is not.
* **Never open the user's profile.** A second Chromium on the default profile
  silently hands off to the running instance and drops `--remote-debugging-port`,
  which is why the helper uses `~/.local/share/chromium-agent`.
* **Credentials stay with the user.** Launch the page, ask them to sign in in the
  window on their screen, then continue over CDP. Never request a password or an
  emailed login code in chat.
* **`:9222` is not a website.** `http://127.0.0.1:9222/json/version` is the
  diagnostic; a blank page in a browser is expected and harmless.
* **Never expose either port off-host.** A CDP port is full control of that
  browser, including its cookies.

---

## 🧪 Grounded UAT Testing (`playwright-rs uat`)

Run intent-based user acceptance testing with the local decision model:

```bash
# Sifts DOM targets, picks the action via JEV (:8083), executes, and verifies:
playwright-rs uat "http://localhost:3000" \
  --goal "submit contact form" \
  --expect-text "Message received" \
  --screenshot /tmp/result.png
```

**Clicking waits, and proves the effect.** `click` polls until the element is
attached, visible, enabled and actually the thing a pointer would hit — then, if
you asked for an expectation, it polls that too and only reports `ok` when the
page changed:

```bash
playwright-rs click "#go" --expect-text "order placed" --json
# { "ok": true, "waited_ms": 706, "effects": ["text:order placed"], … }

playwright-rs click "#buy" --timeout 1500
# Error: "#buy was never clickable within 1500ms (covered by div)"
```

Without an expectation a click only tells you the element existed. With one, it
tells you something happened — which is the only thing worth verifying. The same
polling applies to `uat --expect-text/--expect-url`: a route change that lands
300 ms later no longer reads as a failure.

**Hand it the target instead of letting it choose.** `--ref` skips the decision
call and clicks the ref you name, which is what a caller with its own judge
needs. `candidates` prints the same ref space without clicking anything:

```bash
# The ref space, in DOM order, exactly as uat sees it:
playwright-rs candidates "http://localhost:3000" --json
# [{"ref": "uat-1", "description": "button 'Back to catalog'"}, …]

# Deterministic click on a ref someone else chose:
playwright-rs uat "http://localhost:3000" --goal "complete the purchase" --ref uat-3 --json
```

A ref that is not on the page fails with the available list rather than clicking
something else. `glitch-cat/frontend-uat` is the reference caller: it extracts
with `candidates`, decides with JEV, then passes `--ref`.

---

## 📦 Traditional E2E Test Runner

When running pre-written TypeScript/JavaScript regression suites:

```bash
# Run committed Playwright test suites
npx playwright test

# Interactive visual debugger & code generator
npx playwright codegen http://localhost:3000
```
