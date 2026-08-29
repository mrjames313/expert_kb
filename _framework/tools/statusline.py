"""
statusline.py — a compact Claude Code status line for expert_kb.

Prints one line:
    `<project> · <role@area | (no role)> · H<n|✓> R<n|✓|–> · ctx <N>k[!] · run /kb-vitals`

  - **H** — what the human owes, project-wide: INBOX "Needs decision" and
    "Awaiting your ack", proposals ready to promote, commons pages awaiting review.
  - **R** — the adopted role's local hygiene: uncompacted pulse.log, pulse.md over
    cap, blocked tasks, finished specs with no outcome.md, stale preload, open
    exchanges. `–` when no role is adopted (nothing to scope the checks to).
  - Colors: green = clear, yellow = hygiene, red = blocking (a decision the human
    owes, or a blocked task). Set `statusline.color: false` in config.yml to
    disable.
  - **ctx** — current context size (thousands of tokens); trailing `!` when past
    the restart threshold — the always-on version of `/kb-vitals`' restart nudge.
  - The `run /kb-vitals` hint appears only when H or R is non-zero.

Cheap enough to run on every render (~0.4ms of scanning inside a ~27ms process,
which is nearly all interpreter startup). Two rules keep it that way: no `yaml`
import, and no unbounded walk. Fast-moving vitals are computed live here; the
three that need a full frontmatter walk (commons review, exchanges, preload
staleness) are read from the snapshot `kb_vitals.refresh_cache` leaves behind —
see `vitals_cache` for who refreshes it and why it's only three writers.

Claude Code passes a JSON payload on stdin (session_id, transcript_path, cwd, …).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import session_state as ss  # light: stdlib only
import vitals_cache as vc  # light: stdlib only

_DEFAULT_THRESHOLD = 400_000
_DEFAULT_PULSE_CAP = 80
_TERMINAL_STATUSES = {"done", "superseded"}

# Basic SGR codes — they follow the reader's terminal theme, unlike 256-color.
_GREEN, _YELLOW, _RED, _DIM, _RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


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


def _config_text(repo_root: Path) -> str:
    """config.yml as raw text — parsed with regexes, never with `yaml`."""
    try:
        return (repo_root / "_framework" / "config.yml").read_text(encoding="utf-8")
    except OSError:
        return ""


def _config_int(text: str, key: str, default: int) -> int:
    m = re.search(rf"{key}:\s*(\d+)", text)
    return int(m.group(1)) if m else default


def _config_section(text: str, name: str) -> str:
    """The indented block under `name:`, so a short key can be scoped to its
    section instead of matching anywhere in the file."""
    m = re.search(rf"^{re.escape(name)}:[^\n]*\n((?:[ \t]+[^\n]*\n|\n)*)", text, re.M)
    return m.group(1) if m else ""


def _use_color(config: str) -> bool:
    """ANSI unless turned off: `NO_COLOR` (the cross-tool convention) or
    `statusline.color: false` for a terminal that shows escape codes raw."""
    if os.environ.get("NO_COLOR"):
        return False
    m = re.search(r"color:\s*(true|false)", _config_section(config, "statusline"), re.I)
    return m.group(1).lower() == "true" if m else True


# --- Vitals: live (cheap) + cached (expensive) ---

def _inbox_counts(repo_root: Path) -> tuple[int, int]:
    """(items needing a decision, items awaiting an ack) — one small read."""
    try:
        lines = (repo_root / "INBOX.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return (0, 0)
    decisions = acks = 0
    section = ""
    for line in lines:
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if line.strip().startswith("- "):
            if section == "needs decision":
                decisions += 1
            elif section == "awaiting your ack":
                acks += 1
    return (decisions, acks)


def _proposals_ready(repo_root: Path) -> int:
    proposed = repo_root / "commons" / "_proposed"
    if not proposed.is_dir():
        return 0
    return sum(1 for d in proposed.glob("*/") if (d / "page.md").is_file())


def human_vitals(repo_root: Path, cache: dict) -> tuple[int, bool]:
    """(count, blocking) for the H indicator.

    Blocking = something is waiting on a decision only the human can make; that
    reads red. Acks, proposals and commons review are hygiene — yellow.
    """
    decisions, acks = _inbox_counts(repo_root)
    count = decisions + acks + _proposals_ready(repo_root)
    count += vc.commons_awaiting_review(cache)
    return (count, decisions > 0)


def _pulse_vitals(area_dir: Path, cap: int) -> int:
    count = 0
    pulse_log = area_dir / "_journal" / "pulse.log"
    try:
        if pulse_log.stat().st_size > 0:
            count += 1
    except OSError:
        pass
    pulse_md = area_dir / "pulse.md"
    try:
        if len(pulse_md.read_text(encoding="utf-8").splitlines()) > cap:
            count += 1
    except OSError:
        pass
    return count


def _spec_vitals(area_dir: Path) -> tuple[int, bool]:
    """(count, any_blocked) across the area's specs — small reads, bounded by
    the number of specs."""
    count = 0
    blocked = False
    specs = area_dir / "specs"
    if not specs.is_dir():
        return (0, False)
    for spec_dir in specs.glob("*/"):
        tasks = spec_dir / "tasks.md"
        try:
            lines = tasks.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        statuses = [
            line.strip()[len("_Status:_"):].strip().lower()
            for line in lines if line.strip().startswith("_Status:_")
        ]
        if not statuses:
            continue
        if "blocked" in statuses:
            count += 1
            blocked = True
        if all(s in _TERMINAL_STATUSES for s in statuses) and not (spec_dir / "outcome.md").is_file():
            count += 1
    return (count, blocked)


def role_vitals(repo_root: Path, state: dict, cache: dict, cap: int) -> tuple[int | None, bool]:
    """(count, blocking) for the R indicator; count is None when no role is
    adopted — there's nothing to scope the checks to, which is not the same as
    "clear". A blocked task reads red; the rest is hygiene.

    Context bloat is deliberately excluded: it has its own display (`ctx …!`).
    """
    area = state.get("area")
    if not area:
        return (None, False)
    area_dir = repo_root / area

    count = _pulse_vitals(area_dir, cap)
    spec_count, blocked = _spec_vitals(area_dir)
    count += spec_count
    count += vc.exchange_counts(cache, area)

    role = state.get("role")
    if role:
        # Briefs are owed by the role, not the area — count only this one's.
        count += vc.open_briefs(cache, area, role)

    # Stale preload: the cache holds the newest `updated` across the role's
    # preload; whether that's stale depends on when *this* session adopted.
    started = str(state.get("started_at") or "")[:10]
    if role and started:
        newest = vc.preload_newest_update(cache, area, role)
        if newest and newest > started:
            count += 1

    return (count, blocked)


# --- Rendering ---

def _indicator(label: str, count: int | None, blocking: bool, color: bool) -> str:
    if count is None:
        body, tint = f"{label}–", _DIM
    elif count == 0:
        body, tint = f"{label}✓", _GREEN
    else:
        body, tint = f"{label}{count}", _RED if blocking else _YELLOW
    return f"{tint}{body}{_RESET}" if color else body


def build_line(repo_root: Path, payload: dict) -> str:
    # The payload's session_id keys this session's state file — with several
    # sessions open in one repo, each status line must read its own.
    sid = payload.get("session_id")
    state = ss.read(repo_root, session_id=sid)
    cache = vc.read(repo_root)
    config = _config_text(repo_root)
    color = _use_color(config)

    role = state.get("role")
    area = state.get("area") or ""
    area_short = area.split("/")[-1] if area else ""
    who = f"{role}@{area_short}" if role and area_short else (role or "(no role)")

    h_count, h_blocking = human_vitals(repo_root, cache)
    r_count, r_blocking = role_vitals(
        repo_root, state, cache, _config_int(config, "pulse_line_cap", _DEFAULT_PULSE_CAP)
    )

    tpath = payload.get("transcript_path")
    if tpath:
        tokens = ss.transcript_tokens_tail(tpath)
    else:
        # No transcript in the payload — reconstruct the exact path from session
        # identity (cwd + session_id), never guess from the repo root.
        tokens = ss.context_tokens(
            repo_root, fast=True, cwd=payload.get("cwd"), session_id=sid,
        )

    parts = [
        repo_root.name,
        who,
        _indicator("H", h_count, h_blocking, color)
        + " "
        + _indicator("R", r_count, r_blocking, color),
    ]
    if tokens is not None:
        over = "!" if tokens > _config_int(config, "context_restart_threshold_tokens",
                                           _DEFAULT_THRESHOLD) else ""
        parts.append(f"ctx {tokens // 1000}k{over}")
    if h_count or r_count:
        hint = "run /kb-vitals"
        parts.append(f"{_DIM}{hint}{_RESET}" if color else hint)
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
