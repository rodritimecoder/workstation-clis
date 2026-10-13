#!/usr/bin/env bash
# Wrapper to run hybrid_browser.py using the dedicated virtualenv
VENV="/home/rodri/.gemini/config/skills/hybrid-browser/.venv"
SCRIPT="/home/rodri/.gemini/config/skills/hybrid-browser/scripts/hybrid_browser.py"

exec "$VENV/bin/python" "$SCRIPT" "$@"
