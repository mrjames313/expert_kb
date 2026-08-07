#!/usr/bin/env bash
# pre-compact.sh — fires before Claude Code compacts conversation context.
#
# Conversation compaction can drop tool-call history. To preserve the
# session's work, compact any non-empty pulse logs to disk *now*, before
# the conversation is summarized. The disk state survives compaction; the
# in-context journal might not.
#
# This is mostly equivalent to session-end.sh but is wired to a different
# Claude Code lifecycle event. Compaction can happen mid-session; the agent
# continues afterward.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"

if [ ! -d "$REPO_ROOT/_framework" ]; then
  echo "(pre-compact hook: not in a expert_kb workspace; skipping)" >&2
  exit 0
fi

cd "$REPO_ROOT"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

# Compact any non-empty pulse logs. Unlike session-end, we don't write a
# session_end telemetry event — the session is still in progress.
needs_compact=0
for log in commons/_journal/pulse.log areas/*/_journal/pulse.log; do
  if [ -f "$log" ] && [ -s "$log" ]; then
    needs_compact=1
    break
  fi
done

if [ "$needs_compact" -eq 1 ]; then
  echo "pre-compact hook: flushing pulse logs to pulse.md before context compaction..." >&2
  "$PYTHON" _framework/tools/pulse_compact.py >&2 || true
fi

exit 0
