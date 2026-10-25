---
name: playwright
description: >
  High-performance browser automation, DOM snapshotting, and grounded verification powered by
  native Rust (playwright-rs / fast-cdp). Direct sub-millisecond CDP execution for navigation,
  clicking, typing, accessibility tree snapshots, screenshots, JS evaluation, and automated UAT assertions.
compatibility: "Requires Chromium/Chrome running on :9222 or auto-spawned. Standalone native Rust binary."
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

## 🧪 Grounded UAT Testing (`playwright-rs uat`)

Run intent-based user acceptance testing with the local decision model:

```bash
# Sifts DOM targets, picks the action via JEV (:8083), executes, and verifies:
playwright-rs uat "http://localhost:3000" \
  --goal "submit contact form" \
  --expect-text "Message received" \
  --screenshot /tmp/result.png
```

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
