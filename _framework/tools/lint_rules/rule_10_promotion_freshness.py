"""
Rule 10 — Promotion freshness (warning; default shadowed).

Flags a commons page still `human_reviewed: false` more than
`promotion_freshness_active_days` (default 14) after it was promoted — an ack
that was requested but never happened. This is the aging backstop to the
"Awaiting your ack" INBOX entry `promote.py` files at promotion time
(promotion-protocol.md step 7): that entry is the push signal, this is the catch
if it's ignored (or was never filed by an older tool version).

Commons-extension pages don't trigger it — they land `human_reviewed: true`
(confirmed inline at /add-area time), so there's no pending ack to age.

Self-gating: returns nothing unless
`lint.warnings_visible.rule_10_promotion_freshness` is true
(enable with `/framework enable-lint rule_10_promotion_freshness`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from common import Finding, parse_frontmatter
from activity_days import GitError, active_days_since, is_git_repo

RULE_ID = "rule_10"
SEVERITY = "warning"
CONFIG_KEY = "rule_10_promotion_freshness"


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _age_days(since: date, repo_root: Path) -> int:
    """Active days since `since` in a git repo (per the activity-based-thresholds
    convention); fall back to calendar days when there's no git history to read."""
    if is_git_repo(repo_root):
        try:
            return active_days_since(since, repo_root=repo_root)
        except GitError:
            pass
    return max(0, (date.today() - since).days)


def check(repo_root: Path, config: dict) -> list[Finding]:
    if not config.get("lint", {}).get("warnings_visible", {}).get(CONFIG_KEY, False):
        return []

    threshold = config.get("lint", {}).get("promotion_freshness_active_days", 14)
    findings: list[Finding] = []
    commons_kb = repo_root / "commons" / "kb"
    if not commons_kb.is_dir():
        return findings

    for page in commons_kb.rglob("*.md"):
        if page.name == "index.md":
            continue
        try:
            fm, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not fm or fm.get("human_reviewed") is not False:
            continue  # reviewed, or field absent/true → no pending ack
        promoted_on = _as_date(fm.get("promoted_on"))
        if promoted_on is None:
            continue  # no promotion date to age from
        age = _age_days(promoted_on, repo_root)
        if age > threshold:
            rel = str(page.relative_to(repo_root))
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"promoted {age} active days ago (promoted_on {promoted_on.isoformat()}) "
                    f"but still human_reviewed: false — review it and set human_reviewed: true "
                    f"(threshold {threshold})",
                )
            )
    return findings
