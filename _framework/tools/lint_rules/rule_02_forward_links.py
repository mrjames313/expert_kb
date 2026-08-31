"""
Rule 2 — Forward-link integrity.

- Every [[wikilink]] in a kb page, spec planning file, or data manifest resolves
  to an existing kb page (body and frontmatter alike — a manifest's links live
  entirely in its `context_pages` frontmatter list).
- Every [[wikilink]] in a frontmatter value (e.g. `evidence`, `provenance.ref`,
  `alternatives_considered`, `superseded_by`) resolves too. Frontmatter links
  used to be invisible to lint, which let tools that re-serialize frontmatter
  corrupt them silently.
- A present area prefix (`[[area:target]]`) must name the target's real area.
- Every source page's provenance.raw_path resolves to an existing file.
- Every relative markdown link to a repo path resolves to an existing file
  (the non-wikilink half: code, manifests, raw materials, other specs).

Builds an index of available wikilink targets first, then validates each
forward link from every kb page against it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from common import (
    Finding,
    build_wikilink_index,
    extract_markdown_links,
    extract_wikilinks,
    iter_kb_pages,
    iter_manifest_files,
    iter_spec_files,
    page_area,
    parse_frontmatter,
    split_wikilink,
)

RULE_ID = "rule_02"
SEVERITY = "error"


def _frontmatter_wikilinks(value) -> list[str]:
    """Every [[wikilink]] target in a frontmatter value, recursing through
    dicts and lists. Wikilink values load as strings (see
    common.parse_frontmatter), so extract_wikilinks finds them."""
    found: list[str] = []
    if isinstance(value, str):
        found.extend(extract_wikilinks(value))
    elif isinstance(value, dict):
        for v in value.values():
            found.extend(_frontmatter_wikilinks(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_frontmatter_wikilinks(v))
    return found


def _check_wikilink(
    raw: str, rel: str, repo_root: Path, wikilink_index: dict, where: str
) -> list[Finding]:
    """Validate one wikilink: it must resolve, and a present area prefix must
    match the target's real area. `where` labels the location (`""` for body,
    `"frontmatter "` for frontmatter)."""
    prefix, target = split_wikilink(raw)
    resolved = wikilink_index.get(target)
    if resolved is None:
        return [
            Finding(
                RULE_ID,
                SEVERITY,
                rel,
                f"{where}wikilink [[{raw}]] does not resolve to any kb page",
            )
        ]
    if prefix is not None:
        actual = page_area(resolved, repo_root)
        if actual != prefix:
            return [
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"{where}wikilink [[{raw}]] declares area '{prefix}' but its "
                    f"target resolves to '{actual}'",
                )
            ]
    return []


def _check_markdown_links(
    path: Path, repo_root: Path, body: str, line_offset: int
) -> list[Finding]:
    """Every relative markdown link to a repo path resolves to an existing file.

    This is the non-wikilink half of the link story: `link-conventions.md`
    directs every reference to a file *outside* `kb/` — code, manifests, raw
    materials, another spec's `outcome.md` — to be a relative markdown link, and
    nothing resolved them until now. Destinations that aren't repo paths (URLs,
    anchors, placeholders, code samples) are filtered out by the extractor.
    """
    findings: list[Finding] = []
    rel = str(path.relative_to(repo_root))
    for dest, lineno in extract_markdown_links(body):
        base = repo_root if dest.startswith("/") else path.parent
        target = (base / dest.lstrip("/")).resolve()
        line = line_offset + lineno
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"markdown link ({dest}) points outside the repository",
                    line=line,
                )
            )
            continue
        if not target.exists():
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    rel,
                    f"markdown link ({dest}) does not resolve to an existing file",
                    line=line,
                    suggestion="fix the path, or use a [[wikilink]] if the target is a kb page",
                )
            )
    return findings


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

    # Wikilinks in the body
    for raw in extract_wikilinks(body):
        findings.extend(_check_wikilink(raw, rel, repo_root, wikilink_index, ""))

    # Relative markdown links in the body. Line numbers come from the body, so
    # shift them past the frontmatter block to land on the real file line.
    line_offset = len(text.splitlines()) - len(body.splitlines())
    findings.extend(_check_markdown_links(path, repo_root, body, line_offset))

    # Wikilinks in frontmatter values (evidence, provenance.ref, etc.)
    if fm:
        for raw in _frontmatter_wikilinks(fm):
            findings.extend(
                _check_wikilink(raw, rel, repo_root, wikilink_index, "frontmatter ")
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
    # Spec planning files cite kb pages by wikilink too (see /plan, /replan and
    # the brief template), and a citation that resolves to nothing is the same
    # defect wherever it is written. Non-kb targets — another spec's outcome.md,
    # a code file — are relative markdown links per link-conventions.md, so they
    # are not wikilinks and nothing here looks at them.
    for path in iter_spec_files(repo_root):
        findings.extend(_check_page(path, repo_root, index))
    # Manifests carry `context_pages` — wikilinks into kb naming what gives the
    # data meaning. Rule 12 requires the list be non-empty but never resolved it,
    # so a manifest could point at pages that don't exist.
    for path in iter_manifest_files(repo_root):
        findings.extend(_check_page(path, repo_root, index))
    return findings
