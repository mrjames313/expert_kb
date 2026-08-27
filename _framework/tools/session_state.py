"""
Session state — a small, git-ignored `_session.json` at the repo root holding the
current session's ephemeral state: the adopted role/area, when it was adopted, the
Claude session id and transcript path, and derived signals like context-token
usage. Machine state, not authored content — JSON, like the `.links.json` sidecars.

Lifecycle:
  - `/start`            → `adopt` (merge role/area/started_at).
  - other skills        → `write` extra fields (e.g. last_wrapup_at).
  - session-start hook  → `new_session` (reset role, stamp session_id/transcript).
  - `/clear`/new session → reset happens via the session-start hook.
  - `/kb-vitals`        → `read` + `context_tokens` (role scope + restart signals).

Everything degrades gracefully: a missing/malformed file reads as `{}`, and the
transcript reader (a Claude Code internal — the `~/.claude/projects/…jsonl`
format) returns None rather than raising if anything is off.

Public API:
    session_path(repo_root) -> Path
    read(repo_root) -> dict
    write(repo_root, **fields) -> dict          # merge fields, drop keys set to None
    adopt(repo_root, role, area) -> dict         # merge role/area/started_at=now
    new_session(repo_root, session_id, transcript_path) -> dict  # reset + stamp
    reset(repo_root) -> None                      # delete the file
    transcript_tokens(transcript_path) -> int | None
    find_current_transcript(repo_root) -> Path | None
    context_tokens(repo_root) -> int | None
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

_SESSION_FILE = "_session.json"


def session_path(repo_root: Path) -> Path:
    return Path(repo_root) / _SESSION_FILE


def read(repo_root: Path) -> dict:
    """Return the session state, or {} if absent/unreadable/malformed."""
    path = session_path(repo_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write(repo_root: Path, **fields) -> dict:
    """Merge `fields` into the session file (keys set to None are removed)."""
    state = read(repo_root)
    for key, value in fields.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    session_path(repo_root).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return state


def _now_iso() -> str:
    # datetime.now() is fine here — this is a real runtime stamp, not a workflow value.
    return datetime.now().isoformat(timespec="seconds")


def adopt(repo_root: Path, role: str, area: str) -> dict:
    """Record a role adoption (`/start`). Stamps started_at with the current time."""
    return write(repo_root, role=role, area=area, started_at=_now_iso())


def new_session(repo_root: Path, session_id: str | None, transcript_path: str | None) -> dict:
    """Start-of-session reset: drop any prior role/area, stamp session identity.

    Called by the session-start hook on startup/clear/resume so a fresh session has
    no adopted role until `/start`, while still knowing its own transcript.
    """
    state: dict = {}
    if session_id:
        state["session_id"] = session_id
    if transcript_path:
        state["transcript_path"] = transcript_path
    session_path(repo_root).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return state


def reset(repo_root: Path) -> None:
    """Delete the session file entirely."""
    try:
        session_path(repo_root).unlink()
    except OSError:
        pass


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

    Order: (1) the transcript path recorded in `_session.json` by the hook;
    (2) the exact path reconstructed from `cwd` + `session_id` when a caller
    supplies them (from Claude Code's payload). `fast=True` tail-reads (per-render
    status line); default reads the whole file (on-demand `/kb-vitals`).
    """
    reader = transcript_tokens_tail if fast else transcript_tokens
    recorded = read(repo_root).get("transcript_path")
    if recorded:
        tokens = reader(recorded)
        if tokens is not None:
            return tokens
    exact = transcript_for_session(cwd, session_id)
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

    parser = argparse.ArgumentParser(description="Read/write the session state file.")
    parser.add_argument("--repo", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_adopt = sub.add_parser("adopt", help="record a role adoption (/start)")
    p_adopt.add_argument("--role", required=True)
    p_adopt.add_argument("--area", required=True)

    sub.add_parser("new-session", help="reset + stamp session identity (from hook stdin)")
    p_set = sub.add_parser("set", help="merge one field")
    p_set.add_argument("key")
    p_set.add_argument("value")
    sub.add_parser("clear", help="delete the session file")
    p_show = sub.add_parser("show", help="print current state (+ live context tokens)")
    p_show.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    repo_root = args.repo.resolve() if args.repo else find_repo_root()

    if args.cmd == "adopt":
        adopt(repo_root, args.role, args.area)
    elif args.cmd == "new-session":
        payload = _read_hook_stdin()
        new_session(repo_root, payload.get("session_id"), payload.get("transcript_path"))
    elif args.cmd == "set":
        write(repo_root, **{args.key: args.value})
    elif args.cmd == "clear":
        reset(repo_root)
    elif args.cmd == "show":
        state = dict(read(repo_root))
        state["context_tokens"] = context_tokens(repo_root)
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
        else:
            for k, v in sorted(state.items()):
                print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
