#!/usr/bin/env bash
# Wrapper to run hybrid_browser.py using the dedicated virtualenv.
#
# The venv and the script are resolved relative to this file, not to a
# harness path. The skill is mirrored into three harness directories
# (~/.gemini/config/skills, ~/.config/opencode/skills, ~/.pi/agent/skills),
# so a hardcoded path only worked by accident of the sync and would break
# anywhere else.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/../.venv"
SCRIPT="${SCRIPT_DIR}/hybrid_browser.py"

if [ -x "$VENV/bin/python" ]; then
    exec "$VENV/bin/python" "$SCRIPT" "$@"
fi

echo "warning: no virtualenv at $VENV — falling back to system python" >&2
exec python3 "$SCRIPT" "$@"
