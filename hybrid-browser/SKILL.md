---
name: hybrid-browser
description: >
  Drive a sandboxed Chromium over CDP: navigate, click, type, screenshot.
  Falls back to local vision grounding for canvas, SVG and Shadow DOM.
---

# hybrid-browser

Two paths: a native Rust CDP client (`playwright-rs`, ~3ms cold start) and a
Python wrapper (`hybrid-browser`) that falls back to local DeskForge vision
when the DOM yields no selector.

## Commands

### 1. Start the browser services
```bash
omnicli invoke hybrid-browser/scripts/service -- start
```

### 2. Open a URL (`playwright-rs`)
Native client. Starts a headless engine if none is running.
```bash
playwright-rs open "https://example.com"
```

### 3. Snapshot the page (`playwright-rs`)
Accessibility tree with numbered ref IDs, for clicking by reference.
```bash
playwright-rs snapshot
```

### 4. Click an element (`playwright-rs`)
By ref ID from the snapshot, or by CSS selector.
```bash
playwright-rs click e1
```

### 5. Fill a field and submit (`playwright-rs`)
```bash
playwright-rs fill e2 "search query"
playwright-rs press Enter
```

### 6. Run JavaScript in the page (`playwright-rs`)
```bash
playwright-rs eval "document.title"
```

### 7. Screenshot (`playwright-rs`)
```bash
playwright-rs screenshot /tmp/result.png
```

### 8. Close the session (`playwright-rs`)
```bash
playwright-rs close
```

### 9. Vision-grounded click (`hybrid-browser`)
Use when the element is canvas, SVG, Shadow DOM or obfuscated React.
```bash
hybrid-browser --click "login"
```

### 10. One-shot page verification (`fast-cdp verify`)
Asserts a selector and text in under 40ms.
```bash
fast-cdp verify "http://localhost:3000" --assert-selector "h1" --assert-text "Dashboard"
```

### 11. Goal-directed UAT (`fast-cdp uat`)
Hands the interactive elements to JPT-4B (`:8090`) to decide and click.
```bash
fast-cdp uat "http://localhost:3000" --goal "Proceed to checkout" --expect-text "Checkout Successful"
```

### 12. Interactive REPL (`hybrid-browser`)
Stateful across calls: `goto`, `click`, `type`, `press`, `snap`, `screenshot`.
```bash
hybrid-browser --interactive
```

## Reference

- `references/architecture.md` — tiers, ports (:3010, :9222, :8088), profile path
