"""
Rule 20 — Commons drift (warning; default shadowed).

Flags a commons page whose area source has changed since the two were last
reconciled — the source's `updated` is newer than the commons page's
`aligned_on`. A warning: the source change may not affect the commons copy; a
human judges and reconciles via `/amend-commons`.

Self-gating: returns nothing unless `lint.warnings_visible.rule_20_commons_drift`
is true (enable with `/framework enable-lint rule_20_commons_drift`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from common import (
    Finding,
    bare_id,
    build_wikilink_index,
    parse_frontmatter,
)

RULE_ID = "rule_20"
SEVERITY = "warning"
CONFIG_KEY = "rule_20_commons_drift"


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def check(repo_root: Path, config: dict) -> list[Finding]:
    if not config.get("lint", {}).get("warnings_visible", {}).get(CONFIG_KEY, False):
        return []

    findings: list[Finding] = []
    commons_kb = repo_root / "commons" / "kb"
    if not commons_kb.is_dir():
        return findings
    index = build_wikilink_index(repo_root)

    for page in commons_kb.rglob("*.md"):
        if page.name == "index.md":
            continue
        try:
            fm, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not fm:
            continue
        rel = str(page.relative_to(repo_root))
        aligned = _as_date(fm.get("aligned_on"))
        src = fm.get("promoted_from_page")

        # A commons page we can't drift-check must say so loudly. Silently
        # skipping it reads as "no drift" (a false negative): a user who enables
        # this rule and sees `lint: clean` would wrongly conclude commons is
        # reconciled when it was never checked. These findings also tell an
        # upgrading project exactly which pages need the twin-edge backfill
        # (see UPGRADING.md "Release 2026-08-15").
        if not src:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    "cannot check for drift: no `promoted_from_page` link to a source "
                    "page — backfill it (via /amend-commons) so drift detection can run",
                )
            )
            continue
        if aligned is None:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    "cannot check for drift: missing `aligned_on` — backfill it (via "
                    "/amend-commons, or the upgrade migration) so drift detection can run",
                )
            )
            continue

        sources = src if isinstance(src, list) else [src]
        for s in sources:
            sid = bare_id(str(s))
            src_page = index.get(sid)
            if src_page is None:
                findings.append(
                    Finding(
                        RULE_ID,
                        SEVERITY,
                        rel,
                        f"cannot check for drift: source {sid!r} "
                        "(`promoted_from_page`) not found in the kb",
                    )
                )
                continue
            try:
                sfm, _ = parse_frontmatter(src_page.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            src_updated = _as_date((sfm or {}).get("updated"))
            if src_updated and src_updated > aligned:
                findings.append(
                    Finding(
                        RULE_ID,
                        SEVERITY,
                        rel,
                        f"source {sid!r} changed on {src_updated.isoformat()}, after this "
                        f"page's aligned_on {aligned.isoformat()}; reconcile via /amend-commons",
                    )
                )
    return findings
