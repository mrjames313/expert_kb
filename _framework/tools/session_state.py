"""
Session state — small, git-ignored per-session files under `_session/` at the repo
root, each holding one session's ephemeral state: the adopted role/area, when it
was adopted, the Claude session id and transcript path, and derived signals like
context-token usage. Machine state, not authored content — JSON, like the
`.links.json` sidecars.

**One file per session** (`_session/<session-id>.json`). Two Claude Code sessions
in the same repo (say a researcher and a reviewer) are independent conversations
with independent roles, so a single shared file would let each silently overwrite
the other's role/area/transcript. Sharding on the session id removes the shared
write target entirely — no races, no locking. Every consumer knows its own id:
agent-invoked tools read `$CLAUDE_CODE_SESSION_ID` from the environment, while
hooks and the status line get `session_id` in their stdin payload. When neither is
available (a plain shell, a test), the key falls back to `default`.

Lifecycle:
  - `/start`            → `adopt` (merge role/area/started_at).
  - other skills        → `write` extra fields (e.g. last_wrapup_at).
  - session-start hook  → `new_session` (reset role, stamp session_id/transcript)
                          and `sweep_stale` (retire files from dead sessions).
  - session-end hook    → `reset` (drop this session's file).
  - `/kb-vitals`        → `read` + `context_tokens` (role scope + restart signals).

Everything degrades gracefully: a missing/malformed file reads as `{}`, and the
transcript reader (a Claude Code internal — the `~/.claude/projects/…jsonl`
format) returns None rather than raising if anything is off.

Public API (`session_id` defaults to the current session throughout):
    current_session_id() -> str | None            # $CLAUDE_CODE_SESSION_ID
    session_dir(repo_root) -> Path
    session_path(repo_root, session_id=None) -> Path
    read(repo_root, session_id=None) -> dict
    write(repo_root, *, session_id=None, **fields) -> dict  # merge; None drops a key
    adopt(repo_root, role, area, session_id=None) -> dict   # role/area/started_at=now
    new_session(repo_root, session_id, transcript_path) -> dict  # reset + stamp
    reset(repo_root, session_id=None) -> None      # delete this session's file
    sweep_stale(repo_root, max_age_days=7) -> int  # retire dead sessions' files
    transcript_tokens(transcript_path) -> int | None
    transcript_for_session(cwd, session_id) -> Path | None
    context_tokens(repo_root, *, fast, cwd, session_id) -> int | None
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

_SESSION_DIR = "_session"
_DEFAULT_SID = "default"


def current_session_id() -> str | None:
    """This session's Claude Code id, which the CLI exports into the shells it
    runs. None outside Claude Code (a plain terminal, CI, a test)."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def _resolve_sid(session_id: str | None = None) -> str:
    """The session key for a call: the explicit id, else this session's, else
    `default`. Sanitized — the id arrives from the environment or a hook payload
    and is used as a path component, so it must stay a bare filename."""
    raw = str(session_id or current_session_id() or _DEFAULT_SID)
    return re.sub(r"[^A-Za-z0-9_-]", "-", raw).lstrip("-") or _DEFAULT_SID


def session_dir(repo_root: Path) -> Path:
    return Path(repo_root) / _SESSION_DIR


def session_path(repo_root: Path, session_id: str | None = None) -> Path:
    return session_dir(repo_root) / f"{_resolve_sid(session_id)}.json"


def read(repo_root: Path, session_id: str | None = None) -> dict:
    """Return one session's state, or {} if absent/unreadable/malformed."""
    path = session_path(repo_root, session_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_file(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _merge(repo_root: Path, session_id: str | None, fields: dict) -> dict:
    state = read(repo_root, session_id)
    for key, value in fields.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    _write_file(session_path(repo_root, session_id), state)
    return state


def write(repo_root: Path, *, session_id: str | None = None, **fields) -> dict:
    """Merge `fields` into a session's file (keys set to None are removed).

    `session_id` selects *which* session file to write — it is a routing key, not
    one of the merged fields (only `new_session` stamps the id into the state).
    """
    return _merge(repo_root, session_id, fields)


def _now_iso() -> str:
    # datetime.now() is fine here — this is a real runtime stamp, not a workflow value.
    return datetime.now().isoformat(timespec="seconds")


def adopt(repo_root: Path, role: str, area: str, session_id: str | None = None) -> dict:
    """Record a role adoption (`/start`). Stamps started_at with the current time."""
    return _merge(repo_root, session_id,
                  {"role": role, "area": area, "started_at": _now_iso()})


def new_session(repo_root: Path, session_id: str | None, transcript_path: str | None) -> dict:
    """Start-of-session reset: drop any prior role/area, stamp session identity.

    Called by the session-start hook on startup/clear/resume so a fresh session has
    no adopted role until `/start`, while still knowing its own transcript. Writes
    (and keys) the file on the payload's `session_id` — a resumed session reuses
    its own file, a new one gets its own.
    """
    state: dict = {}
    if session_id:
        state["session_id"] = session_id
    if transcript_path:
        state["transcript_path"] = transcript_path
    _write_file(session_path(repo_root, session_id), state)
    return state


def reset(repo_root: Path, session_id: str | None = None) -> None:
    """Delete one session's file entirely."""
    try:
        session_path(repo_root, session_id).unlink()
    except OSError:
        pass


def sweep_stale(repo_root: Path, max_age_days: int = 7) -> int:
    """Delete session files untouched for `max_age_days`; return how many.

    Sessions usually end without ceremony (a closed terminal, a crash), so the
    session-end hook can't be relied on to clean up. This is the backstop, run at
    session start. The *current* session's file is never swept, however old — a
    long-lived session's file may not have been written since `/start`.
    """
    cutoff = time.time() - max_age_days * 86400
    keep = session_path(repo_root, None)
    removed = 0
    try:
        candidates = sorted(session_dir(repo_root).glob("*.json"))
    except OSError:
        return 0
    for path in candidates:
        if path == keep:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


# --- Transcript / context-length (Claude Code internal; isolated + defensive) ---

def _find_usage(obj) -> dict | None:
    """Locate a usage dict (with input_tokens) in a transcript line object."""
    if not isinstance(obj, dict):
        return None
    for candidate in (obj.get("usage"), obj.get("message", {}).get("usage")
                      if isinstance(obj.get("message"), dict) else None):
        if isinstance(candidate, dict) and "input_tokens" in candidate:
            return candidate
    return None


def _scan_usage(text: str) -> int | None:
    """Sum the input+cache tokens of the last usage record in `text`, or None."""
    for line in reversed(text.splitlines()):
        if '"usage"' not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = _find_usage(obj)
        if usage:
            return (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
            )
    return None


def transcript_tokens(transcript_path) -> int | None:
    """Current context size = input + cache_creation + cache_read tokens of the
    most recent turn. Reads the whole transcript — fine on demand (`/kb-vitals`).
    None if unavailable.
    """
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        return _scan_usage(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def transcript_tokens_tail(transcript_path, tail_bytes: int = 65536) -> int | None:
    """Like `transcript_tokens` but reads only the last `tail_bytes` — cheap enough
    to call per status-line render on a multi-MB transcript. The most recent usage
    record is at the very end, so the tail is all that's needed.
    """
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                f.readline()  # discard the partial line at the seek point
            chunk = f.read()
    except OSError:
        return None
    return _scan_usage(chunk.decode("utf-8", errors="replace"))


def transcript_for_session(cwd, session_id) -> Path | None:
    """The *exact* transcript path for a session. Claude Code stores it at
    ~/.claude/projects/<munged-cwd>/<session_id>.jsonl, munging non-alphanumeric
    chars in the **session cwd** (the launch directory — NOT the repo root, which
    can differ) to '-'. Deterministic: keyed on session identity, so no mtime
    guessing and no cross-session ambiguity. None if cwd/session_id are missing or
    the file doesn't exist.

    (Both inputs come from Claude Code's payload — the hook/status-line stdin. A
    caller without them cannot determine the transcript and should get None rather
    than a guess: guessing from the repo root read an unrelated session's context.)
    """
    if not cwd or not session_id:
        return None
    munged = re.sub(r"[^a-zA-Z0-9]", "-", str(cwd))
    path = Path.home() / ".claude" / "projects" / munged / f"{session_id}.jsonl"
    return path if path.is_file() else None


def context_tokens(
    repo_root: Path, *, fast: bool = False, cwd=None, session_id=None
) -> int | None:
    """Current context size for this session, or None if it can't be determined
    from an authoritative source. Never guesses — a wrong number is worse than none.

    Order: (1) the transcript path the hook recorded in *this session's* state
    file; (2) the exact path reconstructed from `cwd` + `session_id` when a caller
    supplies them (from Claude Code's payload). `fast=True` tail-reads (per-render
    status line); default reads the whole file (on-demand `/kb-vitals`).
    """
    reader = transcript_tokens_tail if fast else transcript_tokens
    recorded = read(repo_root, session_id).get("transcript_path")
    if recorded:
        tokens = reader(recorded)
        if tokens is not None:
            return tokens
    # Reconstruction needs the *real* Claude session id, never the `default` key.
    exact = transcript_for_session(cwd, session_id or current_session_id())
    if exact is not None:
        return reader(exact)
    return None


# --- CLI (used by /start and the session-start hook) ---

def _read_hook_stdin() -> dict:
    """Parse the hook JSON payload from stdin (session-start passes it through)."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        text = sys.stdin.read()
    except OSError:
        return {}
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from common import find_repo_root

    # --session-id is available on every subcommand; it defaults to this session
    # (the CLAUDE_CODE_SESSION_ID the CLI exports), so callers rarely pass it.
    ident = argparse.ArgumentParser(add_help=False)
    ident.add_argument("--session-id", default=None,
                       help="session to act on (default: $CLAUDE_CODE_SESSION_ID)")

    parser = argparse.ArgumentParser(description="Read/write this session's state file.")
    parser.add_argument("--repo", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_adopt = sub.add_parser("adopt", parents=[ident], help="record a role adoption (/start)")
    p_adopt.add_argument("--role", required=True)
    p_adopt.add_argument("--area", required=True)

    sub.add_parser("new-session", help="reset + stamp session identity (from hook stdin)")
    p_set = sub.add_parser("set", parents=[ident], help="merge one field")
    p_set.add_argument("key")
    p_set.add_argument("value")
    sub.add_parser("clear", parents=[ident],
                   help="delete a session's file (id from --session-id, hook stdin, or env)")
    p_sweep = sub.add_parser("sweep", help="delete state files left by dead sessions")
    p_sweep.add_argument("--max-age-days", type=int, default=7)
    p_show = sub.add_parser("show", parents=[ident],
                            help="print this session's state (+ live context tokens)")
    p_show.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    repo_root = args.repo.resolve() if args.repo else find_repo_root()

    if args.cmd == "adopt":
        adopt(repo_root, args.role, args.area, session_id=args.session_id)
    elif args.cmd == "new-session":
        payload = _read_hook_stdin()
        new_session(repo_root, payload.get("session_id"), payload.get("transcript_path"))
        # Fold the sweep in here: session start is the one moment every session
        # passes through, and it saves the hook a second interpreter launch.
        try:
            sweep_stale(repo_root)
        except OSError:
            pass
    elif args.cmd == "set":
        _merge(repo_root, args.session_id, {args.key: args.value})
    elif args.cmd == "clear":
        # The session-end hook pipes its payload in; a human runs this bare.
        sid = args.session_id or _read_hook_stdin().get("session_id")
        reset(repo_root, session_id=sid)
    elif args.cmd == "sweep":
        print(sweep_stale(repo_root, args.max_age_days))
    elif args.cmd == "show":
        state = dict(read(repo_root, args.session_id))
        state["context_tokens"] = context_tokens(repo_root, session_id=args.session_id)
        state["state_file"] = str(session_path(repo_root, args.session_id))
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
        else:
            for k, v in sorted(state.items()):
                print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
