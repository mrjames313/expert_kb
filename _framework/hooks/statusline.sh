#!/usr/bin/env bash
# statusline.sh — Claude Code status line for expert_kb.
#
# Claude Code invokes this frequently (per render) and passes a JSON payload on
# stdin; the first line of stdout becomes the status line. Keep it cheap.
# Never fail: on any problem, print nothing and exit 0.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"
[ -d "$REPO_ROOT/_framework" ] || exit 0
cd "$REPO_ROOT" || exit 0

PAYLOAD=""
if [ ! -t 0 ]; then PAYLOAD="$(cat)"; fi

if [ -x ".venv/bin/python" ]; then PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then PYTHON="python3"
else PYTHON="python"; fi

printf '%s' "$PAYLOAD" | "$PYTHON" _framework/tools/statusline.py 2>/dev/null || true
