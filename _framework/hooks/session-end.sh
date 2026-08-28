#!/usr/bin/env bash
# session-end.sh — fires when a Claude Code session ends.
#
# Safety net: if the agent didn't run /wrap-up, compact any non-empty pulse
# logs and record session_end telemetry without citation/load data (we have
# no agent to ask).
#
# This is strictly best-effort — the agent's /wrap-up does this with full
# citation tracking. The hook just keeps the project from accumulating
# uncompacted state across sessions.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"

if [ ! -d "$REPO_ROOT/_framework" ]; then
  echo "(session-end hook: not in a expert_kb workspace; skipping)" >&2
  exit 0
fi

cd "$REPO_ROOT"

# Claude Code passes a JSON payload on stdin (session_id, transcript_path, reason).
# Read it once, here, before anything else consumes stdin — it identifies which
# session's state file to retire below. Only when piped (a real hook invocation).
HOOK_JSON=""
if [ ! -t 0 ]; then HOOK_JSON="$(cat)"; fi

# Locate python (project venv preferred)
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

# Check if any pulse log is non-empty
needs_compact=0
for log in commons/_journal/pulse.log areas/*/_journal/pulse.log; do
  if [ -f "$log" ] && [ -s "$log" ]; then
    needs_compact=1
    break
  fi
done

if [ "$needs_compact" -eq 1 ]; then
  echo "session-end hook: uncompacted pulse logs detected; compacting..." >&2
  if ! "$PYTHON" _framework/tools/pulse_compact.py 2>&1 | tail -10 >&2; then
    echo "session-end hook: pulse_compact returned non-zero; manual /wrap-up recommended next session" >&2
  fi
fi

# Record session_end telemetry if a session marker exists. The agent's
# /wrap-up would normally do this with cited/loaded data; the hook does it
# without that data so the session at least gets closed out in telemetry.
if [ -f "_framework/telemetry/.current-session" ]; then
  "$PYTHON" _framework/tools/telemetry.py session-end >/dev/null 2>&1 || true
fi

# Retire this session's state file (_session/<session-id>.json) — the id comes
# from the payload, so a concurrent session's state is left alone. Best-effort:
# sessions also die without this hook, which the start-of-session sweep covers.
printf '%s' "$HOOK_JSON" | "$PYTHON" _framework/tools/session_state.py clear >/dev/null 2>&1 || true

exit 0
