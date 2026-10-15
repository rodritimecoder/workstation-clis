---
name: "{HUB_NAME}"
description: "{HUB_DESCRIPTION}"
---

# `{HUB_NAME}` — Unified Workstation Hub

Late-binding Uber OmniMCP discovery and execution gateway bridging native standalone suites.

## Bridged Suites

{SUITES_MARKDOWN_TABLE}

## Usage

```bash
# 1. Discover capabilities
{HUB_NAME} search "intent"

# 2. View all bridged suites
{HUB_NAME} list

# 3. Read specific contract on-demand without context bloat
{HUB_NAME} inspect <suite>

# 4. Execute with response projection and disk buffering
{HUB_NAME} run <suite> [args] [--out file.txt] [--project field1,field2]

# 5. Direct suite shortcut
{HUB_NAME} <suite> [args]
```
