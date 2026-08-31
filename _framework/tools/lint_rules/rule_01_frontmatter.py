"""
Rule 1 — Frontmatter validity.

Checks for every kb page and manifest:
- Frontmatter block is present and parses as YAML mapping.
- Required fields are present.
- `type` is a valid value.
- `status` is a valid value for the type.
- `created` and `updated` are ISO 8601 dates.
- `id` matches the <type-prefix>-YYYY-MM[-DD]-<slug> convention.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from common import (
    Finding,
    REQUIRED_FIELDS_ALL,
    VALID_STATUSES_BY_TYPE,
    VALID_TYPES,
    is_iso_date,
    is_valid_id,
    iter_kb_pages,
    iter_manifest_files,
    iter_spec_files,
    parse_frontmatter,
)

RULE_ID = "rule_01"
SEVERITY = "error"


def _check_page(path: Path, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(path.relative_to(repo_root))

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        findings.append(Finding(RULE_ID, SEVERITY, rel, f"could not read file: {e}"))
        return findings

    try:
        fm, _body = parse_frontmatter(text)
    except yaml.YAMLError as e:
        findings.append(Finding(RULE_ID, SEVERITY, rel, f"malformed frontmatter: {e}", line=1))
        return findings

    if fm is None:
        findings.append(Finding(RULE_ID, SEVERITY, rel, "missing frontmatter block", line=1))
        return findings

    # Required fields
    missing = REQUIRED_FIELDS_ALL - set(fm.keys())
    for field_name in sorted(missing):
        findings.append(
            Finding(RULE_ID, SEVERITY, rel, f"missing required frontmatter field: {field_name}", line=1)
        )

    # Type validity
    page_type = fm.get("type")
    if page_type is not None and page_type not in VALID_TYPES:
        findings.append(
            Finding(
                RULE_ID,
                SEVERITY,
                rel,
                f"invalid type: {page_type!r}",
                line=1,
                suggestion=f"valid types: {', '.join(sorted(VALID_TYPES))}",
            )
        )

    # Status validity
    page_status = fm.get("status")
    if page_type in VALID_STATUSES_BY_TYPE and page_status is not None:
        valid_statuses = VALID_STATUSES_BY_TYPE[page_type]
        if page_status not in valid_statuses:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"invalid status {page_status!r} for type {page_type!r}",
                    line=1,
                    suggestion=f"valid statuses for {page_type}: {', '.join(sorted(valid_statuses))}",
                )
            )

    # ISO dates
    for date_field in ("created", "updated"):
        if date_field in fm:
            if not is_iso_date(fm[date_field]):
                findings.append(
                    Finding(
                        RULE_ID,
                        SEVERITY,
                        rel,
                        f"{date_field} must be YYYY-MM-DD, got {fm[date_field]!r}",
                        line=1,
                    )
                )

    # ID convention
    page_id = fm.get("id")
    if page_id is not None and page_type in VALID_TYPES:
        if not is_valid_id(page_id, page_type):
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"id {page_id!r} does not match convention for type {page_type!r}",
                    line=1,
                    suggestion=f"expected pattern: <prefix>-YYYY-MM[-DD]-<slug> or <prefix>-commons-<slug>",
                )
            )

    return findings


def _check_structural_only(path: Path, repo_root: Path) -> list[Finding]:
    """
    For files where frontmatter is OPTIONAL (spec planning files): only flag
    structural issues — malformed YAML, duplicate frontmatter blocks.
    Doesn't require any specific fields.

    Plain-prose files with no frontmatter are silently passed.
    """
    findings: list[Finding] = []
    rel = str(path.relative_to(repo_root))

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        findings.append(Finding(RULE_ID, SEVERITY, rel, f"could not read file: {e}"))
        return findings

    # Plain prose without frontmatter — nothing to check
    if not text.lstrip().startswith("---"):
        return findings

    try:
        parse_frontmatter(text)
    except yaml.YAMLError as e:
        findings.append(Finding(RULE_ID, SEVERITY, rel, f"malformed frontmatter: {e}", line=1))

    return findings


def check(repo_root: Path, config: dict) -> list[Finding]:
    """Run rule 1 against all kb pages, manifest files, and spec planning files."""
    findings: list[Finding] = []
    for path in iter_kb_pages(repo_root):
        findings.extend(_check_page(path, repo_root))
    for path in iter_manifest_files(repo_root):
        findings.extend(_check_page(path, repo_root))
    for path in iter_spec_files(repo_root):
        findings.extend(_check_structural_only(path, repo_root))
    return findings
