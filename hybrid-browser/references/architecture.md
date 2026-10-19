# Architecture & Ports

Two tiers for *acting*, split by whether the DOM can yield a selector, plus a
separate deterministic path for *verifying*.

1. **Tier 1 (Fast Path)** — native Playwright accessibility and DOM locators
   over Chrome DevTools Protocol (`:9222`). Instant, token-free clicks.
2. **Tier 2 (Vision Fallback)** — when elements are drawn on `<canvas>`, SVG
   dashboards, Shadow DOM, or obfuscated React widgets, take a screenshot,
   resize via Lanczos even-dimensions, and query the local
   `DeskForge-Qwen3.5-4B` (`:8088`) for normalized `(x, y)` coordinates.

A third path, `fast-cdp verify`, asserts a selector and text in a single
shot and is not a session at all — it neither needs the vision fallback nor
leaves a browser running.

| Component | Endpoint | Purpose |
| :--- | :--- | :--- |
| **Podman Container (`hybrid-browser`)** | `http://127.0.0.1:3010` | Live interactive KasmVNC web desktop (you can watch or log in manually) |
| **Chromium CDP** | `http://127.0.0.1:9222` | Direct Chrome DevTools Protocol, driven by `playwright-rs` |
| **DeskForge Server** | `http://127.0.0.1:8088` | Local `DeskForge-Qwen3.5-4B` on Vulkan, dual RX 9060 XT |

The persistent profile directory is preserved across container restarts at
`~/.local/share/hybrid-browser-profile`.

## The native client

`hybrid-browser` ships a compiled native Rust binary (`fast-cdp-rs`, aliased
as `playwright-rs` and `fast-cdp`) that speaks CDP over WebSockets directly.
It replaces heavyweight Node.js Playwright CLI runs: 3ms cold start versus
183ms, and a 3ms snapshot versus 470ms.

## Multi-session and container attachment

```bash
# Work in a specific named session:
playwright-rs -s work open "https://github.com"
playwright-rs -s work snapshot

# Attach to the running hybrid-browser Podman container (:9222 / KasmVNC :3010):
playwright-rs attach --cdp "http://127.0.0.1:9222"
```
