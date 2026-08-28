"""
statusline.py — a compact Claude Code status line for expert_kb.

Prints one line:  `<project> · <role@area | (no role)> · <⚠N | ✓> · ctx <N>k[!]`
  - ⚠N = pending "human" items (INBOX "Needs decision" + "Awaiting your ack").
  - ctx = current context size (thousands of tokens); trailing `!` when past the
    restart threshold — the always-on version of `/kb-vitals`' restart nudge.

Cheap enough to run on every render: tiny reads only — no yaml import, no full
transcript scan (tail-read), no KB scan. Claude Code passes a JSON payload on
stdin (session_id, transcript_path, cwd, …); used opportunistically.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import session_state as ss  # light: stdlib only

_DEFAULT_THRESHOLD = 400_000


def _payload() -> dict:
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _repo_root(payload: dict) -> Path:
    for base in (Path.cwd(), Path(payload.get("cwd") or ".")):
        try:
            p = base.resolve()
        except OSError:
            continue
        for parent in (p, *p.parents):
            if (parent / "_framework").is_dir():
                return parent
    return Path.cwd()


def _threshold(repo_root: Path) -> int:
    """Read the restart threshold from config.yml without a yaml import."""
    try:
        text = (repo_root / "_framework" / "config.yml").read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_THRESHOLD
    m = re.search(r"context_restart_threshold_tokens:\s*(\d+)", text)
    return int(m.group(1)) if m else _DEFAULT_THRESHOLD


def _pending_human(repo_root: Path) -> int:
    """Count bullets under INBOX "Needs decision" + "Awaiting your ack" (cheap)."""
    try:
        lines = (repo_root / "INBOX.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    count = 0
    in_section = False
    for line in lines:
        if line.startswith("## "):
            in_section = line[3:].strip().lower() in ("needs decision", "awaiting your ack")
            continue
        if in_section and line.strip().startswith("- "):
            count += 1
    return count


def build_line(repo_root: Path, payload: dict) -> str:
    # The payload's session_id keys this session's state file — with several
    # sessions open in one repo, each status line must read its own.
    sid = payload.get("session_id")
    state = ss.read(repo_root, session_id=sid)

    role = state.get("role")
    area = state.get("area") or ""
    area_short = area.split("/")[-1] if area else ""
    who = f"{role}@{area_short}" if role and area_short else (role or "(no role)")

    tpath = payload.get("transcript_path")
    if tpath:
        tokens = ss.transcript_tokens_tail(tpath)
    else:
        # No transcript in the payload — reconstruct the exact path from session
        # identity (cwd + session_id), never guess from the repo root.
        tokens = ss.context_tokens(
            repo_root, fast=True, cwd=payload.get("cwd"), session_id=sid,
        )

    parts = [repo_root.name, who]
    pending = _pending_human(repo_root)
    parts.append(f"⚠{pending}" if pending else "✓")
    if tokens is not None:
        over = "!" if tokens > _threshold(repo_root) else ""
        parts.append(f"ctx {tokens // 1000}k{over}")
    return " · ".join(parts)


def main() -> int:
    payload = _payload()
    try:
        print(build_line(_repo_root(payload), payload))
    except Exception:  # noqa: BLE001 — a status line must never error out
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
