"""
Rule 21 — Commons twin-link preference (warning; default shadowed).

Flags a commons page that cites an area page which has a commons twin — it
should prefer the twin so commons stays self-contained and project-wide
backlinks land on the twin, not the area original. A warning: occasional
cross-area reads are acceptable; rewrite via `commons_links.py` / `/amend-commons`.

Self-gating: returns nothing unless
`lint.warnings_visible.rule_21_commons_twin_links` is true.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from common import (
    Finding,
    build_twin_resolver,
    extract_wikilinks,
    parse_frontmatter,
)

RULE_ID = "rule_21"
SEVERITY = "warning"
CONFIG_KEY = "rule_21_commons_twin_links"


def check(repo_root: Path, config: dict) -> list[Finding]:
    if not config.get("lint", {}).get("warnings_visible", {}).get(CONFIG_KEY, False):
        return []

    findings: list[Finding] = []
    commons_kb = repo_root / "commons" / "kb"
    if not commons_kb.is_dir():
        return findings
    resolve_twin = build_twin_resolver(repo_root)

    for page in commons_kb.rglob("*.md"):
        if page.name == "index.md":
            continue
        try:
            _fm, body = parse_frontmatter(page.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        rel = str(page.relative_to(repo_root))
        seen: set[str] = set()
        for raw in extract_wikilinks(body):
            twin = resolve_twin(raw)
            if twin and raw not in seen:
                seen.add(raw)
                findings.append(
                    Finding(
                        RULE_ID,
                        SEVERITY,
                        rel,
                        f"cites [[{raw}]], which has a commons twin [[{twin}]] — prefer the twin",
                    )
                )
    return findings
