---
name: playwright
description: >
  Agent-facing browser control through Padamson's playwright-rust API: CDP attach, Playwright
  locators, AI-mode accessibility refs, screenshots, and JavaScript evaluation. Use frontend-uat
  for the JEV-driven user-journey workflow; use the upstream Rust skill when authoring Rust tests.
compatibility: "Needs a Chromium CDP endpoint: the headless shell on :9222 for unattended work, or a headed Chromium on :9224 when a person must see and drive the page. The CLI wraps playwright-rs 0.20.1 and its bundled Playwright driver."
allowed-tools: "Bash(playwright-rs:*) Bash(fast-cdp:*) Bash(python3:*) Bash(npx:*) Read Write"
---

# Playwright Browser (`playwright`)

> Browser control through the upstream `playwright-rs` Rust API, with a compact local CLI for agent use.

---

## Browser backend

The CLI is built on [`playwright-rs`](https://github.com/padamson/playwright-rust) 0.20.1. It attaches to Chromium over CDP and uses Playwright's locator actionability, AI-mode ARIA snapshots, and `get_by_ref` support. The crate launches its bundled Playwright driver; this is not the old raw-WebSocket CDP implementation.

The CLI keeps the agent-facing commands and the `fast-cdp` alias. The legacy raw-CDP executable is retained as `legacy-fast-cdp` for daemon lifecycle and rollback while the new backend is in use.

---

## CLI quickstart

The local wrapper is available as **`playwright-rs`** and **`fast-cdp`**:

```bash
# Start the unattended browser and open a persistent agent session
playwright-rs daemon start

playwright-rs open "http://localhost:3000"
playwright-rs goto "http://localhost:3000/dashboard"

# AI-mode accessibility snapshot (Playwright refs such as e1, e2)
playwright-rs snapshot

# Interact with a snapshot ref or selector; actions use Playwright locators
playwright-rs click e1
playwright-rs fill e2 "admin@example.com"
playwright-rs type "password123"
playwright-rs press Enter

# 5. Evaluate JavaScript directly in page context
playwright-rs eval "document.title"
playwright-rs eval "window.location.pathname"

# 6. Capture a screenshot of the selected page
playwright-rs screenshot /tmp/screen.png

# 7. One-shot verification assertion (exits 0 on pass, 1 on fail)
playwright-rs verify "http://localhost:3000" --assert-text "Dashboard Overview"

# Close the selected tab/session
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
with the automation shell. Chromium 136+ will not enable remote debugging on its
default profile. If the daily browser was started without a CDP port, the helper
cannot attach to that already-running window. It can make a **one-time local
copy** of the profile, then launch a separate visible browser from that copy.
The copy includes private browser state, is not kept in sync, and may not make
OS-encrypted credentials portable.

```bash
# Who owns which port, and is the visible one real?
python3 scripts/desktop_cdp.py doctor
# agent port   : 9224 -> open
#   browser    : Chrome/154.0.8037.92
# automation   : 9222 -> HeadlessChrome/153 (hidden)
# desktop      : pid 7113 no cdp port (default profile)
# desktop      : pid 712232 cdp :9224 /home/rodri/.local/share/chromium-agent

# To reuse the current Flatpak Chromium profile, first close Chromium normally
# and make sure doctor reports no running default-profile desktop browser.
python3 scripts/desktop_cdp.py doctor
python3 scripts/desktop_cdp.py clone-profile

# Or skip the copy and start with a clean agent profile
python3 scripts/desktop_cdp.py launch "https://example.com/account"

# After cloning, start the visible browser with the copied profile
python3 scripts/desktop_cdp.py launch

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
* **Never launch against the live daily profile.** `clone-profile` refuses to
  copy while it sees the default-profile browser running, refuses to overwrite
  a non-empty destination, and skips disposable caches. Close Chromium normally
  before cloning; it does not stop Chromium for you. The clone at
  `~/.local/share/chromium-agent` is separate and will diverge from the daily
  profile after launch.
* **A clone is sensitive.** It contains copied browser data such as cookies and
  browsing state. Keep it local, don't upload or share it, and use `stop` when
  finished. If login state does not transfer, sign in directly in the visible
  agent window rather than copying secret-store files by hand.
* **Credentials stay with the user.** Launch the page, ask them to sign in in the
  window on their screen, then continue over CDP. Never request a password or an
  emailed login code in chat.
* **`:9222` is not a website.** `http://127.0.0.1:9222/json/version` is the
  diagnostic; a blank page in a browser is expected and harmless.
* **Never expose either port off-host.** A CDP port is full control of that
  browser, including its cookies.

---

## Workflow routing

This skill owns browser operations. For an intent-based journey, use the separate
`frontend-uat` skill, which composes this CLI with JEV:

```bash
frontend-uat run --url http://localhost:3000 \
  --intent "submit contact form" \
  --expect-text "Message received" \
  --screenshot /tmp/result.png
```

`frontend-uat` owns candidate extraction, the JEV decision, the `uat-N` ref
contract, evidence ledger, and outcome verification. This CLI supplies the
browser backend and retains `candidates`/`uat --ref` for compatibility.

For a single browser action, use `click` with an expected effect. It waits for
Playwright's actionability checks and reports failure if the requested effect
does not appear:

```bash
playwright-rs click "#go" --expect-text "order placed" --json
```

---

## 📦 Traditional E2E Test Runner

When running pre-written TypeScript/JavaScript regression suites:

```bash
# Run committed Playwright test suites
npx playwright test

# Interactive visual debugger & code generator
npx playwright codegen http://localhost:3000
```

When writing Rust tests against the crate itself, use the local
`playwright-rs-usage` skill (vendored from
[padamson/playwright-rust](https://github.com/padamson/playwright-rust/tree/main/skills/playwright-rs-usage),
Apache-2.0).
