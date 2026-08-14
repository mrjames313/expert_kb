"""
Rule 2 — Forward-link integrity.

- Every [[wikilink]] in a kb page resolves to an existing kb page.
- Every source page's provenance.raw_path resolves to an existing file.

Builds an index of available wikilink targets first, then validates each
forward link from every kb page against it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from common import (
    Finding,
    build_wikilink_index,
    extract_wikilinks,
    iter_kb_pages,
    page_area,
    parse_frontmatter,
    split_wikilink,
)

RULE_ID = "rule_02"
SEVERITY = "error"


def _check_page(
    path: Path, repo_root: Path, wikilink_index: dict[str, Path]
) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(path.relative_to(repo_root))

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return findings  # rule 1 will flag

    try:
        fm, body = parse_frontmatter(text)
    except yaml.YAMLError:
        return findings  # rule 1 will flag

    # Wikilinks in body
    for raw in extract_wikilinks(body):
        prefix, target = split_wikilink(raw)
        resolved = wikilink_index.get(target)
        if resolved is None:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"wikilink [[{raw}]] does not resolve to any kb page",
                )
            )
            continue
        # If the link carries an area prefix, it must name the target's actual
        # area (readability convention; a wrong label is misleading).
        if prefix is not None:
            actual = page_area(resolved, repo_root)
            if actual != prefix:
                findings.append(
                    Finding(
                        RULE_ID,
                        SEVERITY,
                        rel,
                        f"wikilink [[{raw}]] declares area '{prefix}' but its "
                        f"target resolves to '{actual}'",
                    )
                )

    # Source-page raw_path
    if fm and fm.get("type") == "source":
        provenance = fm.get("provenance", {})
        if isinstance(provenance, dict):
            raw_path = provenance.get("raw_path")
            if raw_path:
                # raw_path is repo-root-relative
                resolved = repo_root / raw_path
                if not resolved.is_file():
                    findings.append(
                        Finding(
                            RULE_ID,
                            SEVERITY,
                            rel,
                            f"provenance.raw_path does not resolve: {raw_path}",
                            line=1,
                        )
                    )

    return findings


def check(repo_root: Path, config: dict) -> list[Finding]:
    findings: list[Finding] = []
    index = build_wikilink_index(repo_root)
    for path in iter_kb_pages(repo_root):
        findings.extend(_check_page(path, repo_root, index))
    return findings
