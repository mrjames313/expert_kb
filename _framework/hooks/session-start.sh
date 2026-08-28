#!/usr/bin/env bash
# session-start.sh — fires when Claude Code starts a new session.
#
# Surfaces the orientation files (CLAUDE.md, areas-index.md, INBOX.md) so the
# agent has the project shape in context before any /start invocation. Also
# warns about uncompacted pulse logs left over from a prior session.
#
# Output goes to stdout, which Claude Code prepends to the agent's context.
# Stderr is ignored; never fail the session because the hook had an issue.

set -uo pipefail

# Find repo root: the dir containing _framework/. Walk up from the script
# location, since the script may be invoked from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"

if [ ! -d "$REPO_ROOT/_framework" ]; then
  echo "(session-start hook: not in a expert_kb workspace; skipping)" >&2
  exit 0
fi

cd "$REPO_ROOT"

# --- Session state: reset role/area for the new session, stamp identity ---
# Claude Code passes the hook a JSON payload on stdin (session_id, transcript_path,
# source). Consume it only when piped (a real hook invocation), never when run
# interactively for testing. State lives in _session/<session-id>.json, so this
# writes only *this* session's file and never disturbs a concurrent session's.
# Reset drops any prior role so a cleared/new session has "no role adopted" until
# /start; the transcript stamp powers the context-length signal. `new-session` also
# sweeps state files left behind by sessions that ended without the end hook.
# Best-effort — never fail the session over it.
HOOK_JSON=""
if [ ! -t 0 ]; then HOOK_JSON="$(cat)"; fi
if [ -x ".venv/bin/python" ]; then PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then PYTHON="python3"
else PYTHON="python"; fi
printf '%s' "$HOOK_JSON" | "$PYTHON" _framework/tools/session_state.py new-session >/dev/null 2>&1 || true

# --- Vitals cache: refresh the status line's expensive counts once per session ---
# The status line computes the cheap vitals live but reads commons-review,
# exchange and preload-staleness counts from this snapshot. Refreshing here is
# what bounds their staleness to a single session. ~100ms, best-effort.
"$PYTHON" _framework/tools/kb_vitals.py --refresh-cache >/dev/null 2>&1 || true

# --- CLAUDE.md ---
if [ -f "CLAUDE.md" ]; then
  echo "==== CLAUDE.md ===="
  echo
  cat CLAUDE.md
  echo
  echo
fi

# --- areas-index.md ---
if [ -f "areas-index.md" ]; then
  echo "==== areas-index.md ===="
  echo
  cat areas-index.md
  echo
  echo
fi

# --- INBOX.md ---
if [ -f "INBOX.md" ]; then
  echo "==== INBOX.md ===="
  echo
  cat INBOX.md
  echo
  echo
fi

# --- Uncompacted pulse log check ---
echo "==== Session state ===="
echo

uncompacted=0
# Use a portable null-friendly loop; suppress errors if any path doesn't exist.
for log in commons/_journal/pulse.log areas/*/_journal/pulse.log; do
  if [ -f "$log" ] && [ -s "$log" ]; then
    if [ "$uncompacted" -eq 0 ]; then
      echo "Uncompacted pulse log(s) from a prior session:"
    fi
    echo "  $log ($(wc -l < "$log" | tr -d ' ') lines)"
    uncompacted=$((uncompacted + 1))
  fi
done

if [ "$uncompacted" -gt 0 ]; then
  echo
  echo "→ Run /wrap-up before starting new work, or /start which will offer to do it."
else
  echo "All pulse logs are clean."
fi

# --- Telemetry sanity ---
if [ -f "_framework/telemetry/.current-session" ]; then
  echo
  echo "Note: a session_start marker exists from a prior session that never closed."
  echo "Next /wrap-up will record a session_end against it."
fi

echo
echo "→ Run /start to adopt a role."

exit 0
