"""
kb_vitals.py — scan operational state and surface the recommended next actions,
each with the command to run. Powers `/kb-vitals`.

Two scopes:
  HUMAN (project-wide, always shown): decisions/acks only the human can resolve —
    INBOX "Needs decision", commons pages awaiting review, proposals ready to promote.
  ROLE (current area, from this session's _session/<session-id>.json): local hygiene —
    wrap-up due, pulse over-cap, restart-the-role signals (context bloat, stale
    preload), spec complete → outcome, blocked tasks, exchanges to close.
Framework-level vitals (upgrade currency) are deferred.

Everything is a cheap read; no lint run. Missing inputs are skipped, not errored.

Public API:
    collect(repo_root, config) -> list[Vital]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import session_state  # noqa: E402
import vitals_cache  # noqa: E402
from common import find_repo_root, iter_areas, load_config, parse_frontmatter  # noqa: E402
from token_estimate import parse_role_preload  # noqa: E402

_DEFAULT_CONTEXT_THRESHOLD = 400_000  # tokens; tune to your context window
_TERMINAL_STATUSES = {"done", "superseded"}


@dataclass
class Vital:
    scope: str        # "human" | "role"
    message: str      # what's up + why
    command: str = ""  # the command to run (may be empty)


# --- helpers ---

def _inbox_items(repo_root: Path, heading: str) -> list[str]:
    inbox = repo_root / "INBOX.md"
    if not inbox.is_file():
        return []
    items: list[str] = []
    in_section = False
    for line in inbox.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line[3:].strip().lower() == heading.lower()
            continue
        if in_section and line.strip().startswith("- "):
            items.append(line.strip()[2:])
    return items


def _fm(path: Path) -> dict:
    try:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a malformed page shouldn't break the whole scan
        return {}
    return fm or {}


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _task_statuses(tasks_md: Path) -> list[str]:
    """Return the `_Status:_ <value>` values in a tasks.md (lowercased)."""
    if not tasks_md.is_file():
        return []
    statuses: list[str] = []
    for line in tasks_md.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("_Status:_"):
            statuses.append(s[len("_Status:_"):].strip().lower())
    return statuses


# --- Expensive scans (shared with the status line via the vitals cache) ---

def commons_awaiting_review(repo_root: Path) -> int:
    """Commons pages still carrying `human_reviewed: false`.

    The costliest vital: a frontmatter parse per commons page, growing with the
    KB. Cached for the status line (see `vitals_cache`); computed live here.
    """
    commons_kb = repo_root / "commons" / "kb"
    if not commons_kb.is_dir():
        return 0
    return sum(
        1 for p in commons_kb.rglob("*.md")
        if p.name != "index.md" and _fm(p).get("human_reviewed") is False
    )


def exchange_counts(repo_root: Path, area: str) -> tuple[int, int]:
    """(open exchanges addressed to `area`, answered ones it should close)."""
    ex_dir = repo_root / "exchanges"
    if not ex_dir.is_dir():
        return (0, 0)
    to_close = to_answer = 0
    for q in ex_dir.glob("*/q-*.md"):
        fm = _fm(q)
        status = str(fm.get("status", "")).lower()
        if status == "answered" and fm.get("from_area") == area:
            to_close += 1
        elif status == "open" and fm.get("to_area") == area:
            to_answer += 1
    return (to_answer, to_close)


def preload_newest_update(repo_root: Path, role_file: Path) -> str | None:
    """The most recent `updated` date across a role's full-tier preload, as ISO.

    The status line compares this against its own session's `started_at` to
    decide whether the loaded copies have gone stale — which keeps the
    per-session half of that question out of the shared cache.
    """
    if not role_file.is_file():
        return None
    try:
        preload = parse_role_preload(role_file.read_text(encoding="utf-8")).get("full", [])
    except OSError:
        return None
    newest: date | None = None
    for rel in preload:
        target = repo_root / rel
        upd = _as_date(_fm(target).get("updated")) if target.is_file() else None
        if upd and (newest is None or upd > newest):
            newest = upd
    return newest.isoformat() if newest else None


def refresh_cache(repo_root: Path, config: dict) -> dict:
    """Recompute the expensive vitals for every area and write the cache.

    Called by `/kb-vitals`, by `lint.py` (so `/check` and `/wrap-up` refresh it),
    and once per session by `/start` and the session-start hook. Mutating skills
    deliberately don't call it — see the note in `vitals_cache`.
    """
    multi_area = bool(config.get("capabilities", {}).get("multi_area"))
    areas: dict = {}
    for area_dir in iter_areas(repo_root):
        area = area_dir.relative_to(repo_root).as_posix()
        entry: dict = {}
        if multi_area:
            to_answer, to_close = exchange_counts(repo_root, area)
            entry["exchanges_to_answer"] = to_answer
            entry["exchanges_to_close"] = to_close
        roles: dict = {}
        for role_file in sorted((area_dir / "roles").glob("*/role.md")):
            newest = preload_newest_update(repo_root, role_file)
            if newest:
                roles[role_file.parent.name] = {"preload_newest_update": newest}
        if roles:
            entry["roles"] = roles
        areas[area] = entry

    snapshot = {
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "commons_awaiting_review": commons_awaiting_review(repo_root),
        "areas": areas,
    }
    vitals_cache.write(repo_root, snapshot)
    return snapshot


# --- HUMAN vitals (project-wide) ---

def human_vitals(repo_root: Path) -> list[Vital]:
    vitals: list[Vital] = []

    needs = _inbox_items(repo_root, "Needs decision")
    if needs:
        vitals.append(Vital("human", f"{len(needs)} item(s) need your decision", "review INBOX.md"))

    unreviewed = commons_awaiting_review(repo_root)
    if unreviewed:
        vitals.append(Vital(
            "human",
            f"{unreviewed} promoted commons page(s) awaiting your review",
            "review each and set human_reviewed: true",
        ))

    proposed = repo_root / "commons" / "_proposed"
    if proposed.is_dir():
        pending = [d for d in sorted(proposed.glob("*/")) if (d / "page.md").is_file()]
        if pending:
            slugs = ", ".join(d.name for d in pending[:3]) + (" …" if len(pending) > 3 else "")
            vitals.append(Vital(
                "human",
                f"{len(pending)} proposal(s) ready to promote ({slugs})",
                "/promote <slug>",
            ))

    return vitals


# --- ROLE vitals (current adopted area) ---

def _context_vital(repo_root: Path, config: dict) -> Vital | None:
    """Restart nudge when the live session context is large. Session-scoped — it's
    about the conversation, so it fires whether or not a role is adopted."""
    threshold = config.get("kb_vitals", {}).get(
        "context_restart_threshold_tokens", _DEFAULT_CONTEXT_THRESHOLD
    )
    tokens = session_state.context_tokens(
        repo_root, session_id=session_state.current_session_id()
    )
    if tokens is not None and tokens > threshold:
        return Vital(
            "role",
            f"context ~{tokens // 1000}k tokens (over {threshold // 1000}k) — a fresh context would help",
            "/wrap-up, then restart (quit + relaunch, not just /clear)",
        )
    return None


def role_vitals(repo_root: Path, config: dict) -> list[Vital]:
    # Keyed on this session's id: a second session in the same repo has its own
    # adopted role, and reading its state would scope these checks to the wrong area.
    state = session_state.read(repo_root, session_id=session_state.current_session_id())
    role = state.get("role")
    area = state.get("area")

    vitals: list[Vital] = []

    # Session-level context/restart check — before the no-role return, since it's
    # about the conversation, not the adopted role.
    context = _context_vital(repo_root, config)
    if context:
        vitals.append(context)

    if not area:
        vitals.append(Vital("role", "no role adopted this session", "/start"))
        return vitals

    area_dir = repo_root / area

    # Wrap-up due — uncompacted pulse.log
    pulse_log = area_dir / "_journal" / "pulse.log"
    if pulse_log.is_file() and pulse_log.stat().st_size > 0:
        n = len(pulse_log.read_text(encoding="utf-8").splitlines())
        vitals.append(Vital("role", f"uncompacted pulse.log ({n} lines)", "/wrap-up"))

    # Pulse over-cap
    cap = config.get("lint", {}).get("pulse_line_cap", 80)
    pulse_md = area_dir / "pulse.md"
    if pulse_md.is_file():
        n = len(pulse_md.read_text(encoding="utf-8").splitlines())
        if n > cap:
            vitals.append(Vital("role", f"pulse.md over cap ({n}/{cap})", "/wrap-up"))

    # Restart signal — stale preload (a preload page changed since you adopted)
    started = _as_date(state.get("started_at"))
    if role and started:
        role_file = area_dir / "roles" / role / "role.md"
        if role_file.is_file():
            preload = parse_role_preload(role_file.read_text(encoding="utf-8")).get("full", [])
            stale = 0
            for rel in preload:
                target = repo_root / rel
                upd = _as_date(_fm(target).get("updated")) if target.is_file() else None
                if upd and upd > started:
                    stale += 1
            if stale:
                vitals.append(Vital(
                    "role",
                    f"{stale} preloaded page(s) updated since you adopted — your loaded copy is stale",
                    "re-run /start to refresh",
                ))

    # Specs: complete → outcome, and blocked tasks
    specs = area_dir / "specs"
    if specs.is_dir():
        for spec_dir in sorted(d for d in specs.glob("*/") if d.is_dir()):
            statuses = _task_statuses(spec_dir / "tasks.md")
            if not statuses:
                continue
            if "blocked" in statuses:
                vitals.append(Vital("role", f"spec '{spec_dir.name}' has a blocked task", "/replan or unblock it"))
            if all(s in _TERMINAL_STATUSES for s in statuses) and not (spec_dir / "outcome.md").is_file():
                vitals.append(Vital("role", f"spec '{spec_dir.name}' complete — no outcome.md yet", "/wrap-up (writes outcome.md)"))

    # Exchanges (multi_area only) — answered-not-closed / open-to-you
    if config.get("capabilities", {}).get("multi_area"):
        vitals.extend(_exchange_vitals(repo_root, area))

    return vitals


def _exchange_vitals(repo_root: Path, area: str) -> list[Vital]:
    to_answer, to_close = exchange_counts(repo_root, area)
    vitals: list[Vital] = []
    if to_answer:
        vitals.append(Vital("role", f"{to_answer} open exchange(s) addressed to your area", "/respond-exchange"))
    if to_close:
        vitals.append(Vital("role", f"{to_close} answered exchange(s) to close", "/close-exchange"))
    return vitals


def collect(repo_root: Path, config: dict) -> list[Vital]:
    return human_vitals(repo_root) + role_vitals(repo_root, config)


# --- CLI ---

def _format(vitals: list[Vital]) -> str:
    human = [v for v in vitals if v.scope == "human"]
    role = [v for v in vitals if v.scope == "role"]
    lines = ["kb-vitals", ""]

    def block(title: str, items: list[Vital]) -> None:
        lines.append(f"  {title}")
        if not items:
            lines.append("    ✓ nothing pending")
        for v in items:
            lines.append(f"    • {v.message}")
            if v.command:
                lines.append(f"        → {v.command}")
        lines.append("")

    block("Human — you owe (project-wide):", human)
    block("Role — your area:", role)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Show operational state + recommended next actions.")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--refresh-cache", action="store_true",
        help="recompute the status line's vitals cache and exit (no output)",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo.resolve() if args.repo else find_repo_root()
    config = load_config(repo_root)

    if args.refresh_cache:
        refresh_cache(repo_root, config)
        return 0

    vitals = collect(repo_root, config)

    if args.json:
        print(json.dumps([v.__dict__ for v in vitals], indent=2))
    else:
        print(_format(vitals))

    # This run already paid for most of the expensive scans; leave the status
    # line a fresh snapshot. Never let a cache problem fail the command.
    try:
        refresh_cache(repo_root, config)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
