"""
Vitals cache — a small, git-ignored snapshot of the *expensive* vitals, so the
status line can show them without paying for them on every render.

Why a cache at all. The status line runs on every render, and three of the vitals
need a full frontmatter walk: commons pages awaiting review (~0.4ms per commons
page, unbounded as the KB grows), exchanges, and preload staleness. Together they
cost ~74ms including the `yaml` import — fine once, unacceptable per render. The
other vitals (INBOX, proposals, pulse, specs) are cheap enough to compute live and
are deliberately **not** cached: they move fast, and a stale count is worse than
none. So: fast-moving vitals live, slow-moving vitals cached.

Who writes it (three, deliberately — see `kb_vitals.refresh_cache`):
  - `/kb-vitals`  — computes all of this anyway; the write is the leftover.
  - `lint.py`     — already walks every page, so `/check` and `/wrap-up` refresh it.
  - `/start` + the session-start hook — guarantees a refresh once per session.
Mutating skills (`/promote`, `/exchange`, …) deliberately do not write it: an
enumerated list of writers is a list of places to forget one. Three structural
refresh points bound staleness to a single session, which is well inside the
tolerance of vitals that move on the order of days.

Shape (all keys optional — a reader must degrade to "unknown", never to a wrong
count):

    {
      "computed_at": "2026-08-27T10:14:03",
      "commons_awaiting_review": 2,
      "areas": {
        "areas/research": {
          "exchanges_to_answer": 1,
          "exchanges_to_close": 0,
          "roles": {"researcher": {"preload_newest_update": "2026-08-20"}}
        }
      }
    }

The role half is keyed by area and role because two concurrent sessions can hold
different roles — a flat count would report one session's state to the other.
Preload staleness additionally depends on when *this* session adopted, so the
cache stores the newest `updated` date across the role's preload and the reader
compares it against its own `started_at`. That keeps the per-session half in the
per-session state file, where it belongs.

Stdlib only, by contract: the status line imports this and must not pay for
`yaml`. The computation that fills it lives in `kb_vitals.py`, which may.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_CACHE_PATH = ("_framework", "telemetry", "vitals-cache.json")


def path(repo_root: Path) -> Path:
    return Path(repo_root).joinpath(*_CACHE_PATH)


def read(repo_root: Path) -> dict:
    """The cached snapshot, or {} if absent/unreadable/malformed."""
    try:
        data = json.loads(path(repo_root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write(repo_root: Path, data: dict) -> None:
    """Replace the snapshot atomically.

    The cache is repo-global, so concurrent sessions can write it at once (two
    `/check` runs, say). The counts don't depend on who computed them, so
    last-writer-wins is correct — but a reader must never see a half-written
    file, hence the temp-file swap. Best-effort: a cache write must never break
    the tool that was kind enough to refresh it.
    """
    target = path(repo_root)
    tmp = target.with_suffix(".json.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


# --- Accessors (keep the shape's knowledge in one file) ---

def commons_awaiting_review(cache: dict) -> int:
    value = cache.get("commons_awaiting_review")
    return value if isinstance(value, int) else 0


def for_area(cache: dict, area: str) -> dict:
    areas = cache.get("areas")
    if not isinstance(areas, dict):
        return {}
    entry = areas.get(area)
    return entry if isinstance(entry, dict) else {}


def exchange_counts(cache: dict, area: str) -> int:
    """Open-to-you plus answered-to-close, for the area's exchange vitals."""
    entry = for_area(cache, area)
    total = 0
    for key in ("exchanges_to_answer", "exchanges_to_close"):
        value = entry.get(key)
        if isinstance(value, int):
            total += value
    return total


def preload_newest_update(cache: dict, area: str, role: str) -> str | None:
    """ISO date of the most recently `updated` page in the role's full preload,
    or None when unknown (never computed, or the role isn't in the snapshot)."""
    roles = for_area(cache, area).get("roles")
    if not isinstance(roles, dict):
        return None
    entry = roles.get(role)
    if not isinstance(entry, dict):
        return None
    value = entry.get("preload_newest_update")
    return value if isinstance(value, str) else None
