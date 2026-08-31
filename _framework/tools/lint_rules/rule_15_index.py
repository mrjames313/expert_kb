"""
Rule 15 — Index maintenance (fixup).

Regenerates:
- areas-index.md at repo root: list of areas with summaries and roles
- <area>/kb/index.md per kb directory: catalog of pages grouped by type/status

This is a fixup rule — it writes files and produces findings only on write failures.
A file is rewritten only when its generated content actually changed (the
`_Last regenerated:_` stamp is masked out of the comparison), so a no-op run
leaves the tree clean.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

from common import (
    Finding,
    iter_areas,
    iter_kb_pages,
    iter_role_files,
    parse_frontmatter,
)

RULE_ID = "rule_15"
SEVERITY = "error"


_STAMP_RE = re.compile(r"_Last regenerated: (\d{4}-\d{2}-\d{2})_")


def _effective_stamp(existing_path: Path) -> str:
    """Today's date — unless the file's existing stamp is *newer*, in which case
    keep it. Guards against a clock that trails the previous committer's, which
    would otherwise roll the stamp backwards and produce a spurious diff."""
    today = date.today()
    try:
        m = _STAMP_RE.search(existing_path.read_text(encoding="utf-8"))
        if m:
            prev = date.fromisoformat(m.group(1))
            if prev > today:
                return prev.isoformat()
    except (OSError, ValueError):
        pass
    return today.isoformat()


def _write_if_changed(path: Path, content: str) -> None:
    """Write `content` only if it differs from what's on disk, ignoring the
    `_Last regenerated:_` line.

    Without this, the first lint run on any new day rewrites every index with
    nothing but a date bump. That dirties the tree for a change you didn't make,
    so `/check` before a commit produces a spurious diff; `git status
    --porcelain` stops being a clean signal — which `UPGRADING.md` Step 1
    depends on, so an upgrade can be blocked by lint's own churn; and the noise
    trains you to `git checkout --` reflexively, which is how a real
    regeneration eventually gets discarded by accident.

    Comparing with the stamp masked also makes the stamp mean "last time this
    index actually changed", which is the more useful reading. Same principle as
    `_effective_stamp`, one step further: don't produce diffs you didn't earn.
    """
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        path.write_text(content, encoding="utf-8")  # absent or unreadable — write
        return
    if _STAMP_RE.sub("", existing) == _STAMP_RE.sub("", content):
        return
    path.write_text(content, encoding="utf-8")


def _read_brief_summary(brief_path: Path) -> str:
    """Return the first non-empty, non-heading paragraph from a brief.md."""
    if not brief_path.is_file():
        return ""
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    paragraphs = []
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("_") and stripped.endswith("_"):
            continue  # italicized placeholder
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    if not paragraphs:
        return ""
    # First paragraph, truncated to ~200 chars
    p = paragraphs[0]
    return p if len(p) <= 200 else p[:197] + "..."


def _generate_areas_index(repo_root: Path) -> str:
    """Build the content for areas-index.md."""
    lines = [
        "# Areas Index",
        "",
        "_Auto-maintained by lint; do not edit by hand._",
        f"_Last regenerated: {_effective_stamp(repo_root / 'areas-index.md')}_",
        "",
    ]

    # Commons section
    lines.append("## commons/")
    commons_brief = repo_root / "commons" / "brief.md"
    summary = _read_brief_summary(commons_brief)
    if summary:
        lines.extend(["", summary, ""])
    else:
        lines.extend(["", "_(commons brief not yet populated)_", ""])

    # Commons roles
    commons_roles = sorted((repo_root / "commons" / "roles").glob("*/role.md")) if (repo_root / "commons" / "roles").is_dir() else []
    if commons_roles:
        lines.append("Roles:")
        for role_path in commons_roles:
            role_name = role_path.parent.name
            role_summary = _read_role_summary(role_path)
            lines.append(f"- **{role_name}** — {role_summary}" if role_summary else f"- **{role_name}**")
        lines.append("")

    # Areas
    for area_dir in sorted(iter_areas(repo_root)):
        area_rel = area_dir.relative_to(repo_root)
        depth = len(area_rel.parts) - 2  # areas/X = depth 0, areas/X/Y = depth 1
        prefix = "#" * (3 + depth)  # h3 for top-level area, h4 for sub-area, etc.
        lines.append(f"{prefix} {area_rel}/")
        summary = _read_brief_summary(area_dir / "brief.md")
        if summary:
            lines.extend(["", summary, ""])

        area_roles = sorted((area_dir / "roles").glob("*/role.md")) if (area_dir / "roles").is_dir() else []
        if area_roles:
            lines.append("Roles:")
            for role_path in area_roles:
                role_name = role_path.parent.name
                role_summary = _read_role_summary(role_path)
                lines.append(f"- **{role_name}** — {role_summary}" if role_summary else f"- **{role_name}**")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _read_role_summary(role_path: Path) -> str:
    """Extract `summary` from a role file's frontmatter."""
    try:
        text = role_path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
    except (OSError, yaml.YAMLError):
        return ""
    if fm:
        return str(fm.get("summary", "")).strip()
    return ""


def _generate_kb_index(kb_dir: Path, repo_root: Path) -> str:
    """Build the content for a single kb/index.md."""
    # Group pages by type/status
    groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for page in kb_dir.rglob("*.md"):
        if page.name == "index.md":
            continue
        try:
            text = page.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(text)
        except (OSError, yaml.YAMLError):
            continue
        if not fm:
            continue
        page_type = fm.get("type", "unknown")
        status = fm.get("status", "")

        if page_type == "concept" and status == "under_test":
            groups["concepts_under_test"].append((page, fm))
        elif page_type == "concept":
            groups["concepts_other"].append((page, fm))
        else:
            groups[page_type].append((page, fm))

    area_rel = kb_dir.parent.relative_to(repo_root)
    lines = [
        f"# {area_rel} kb index",
        "",
        "_Auto-generated; do not edit by hand._",
        f"_Last regenerated: {_effective_stamp(kb_dir / 'index.md')}_",
        "",
    ]

    section_order = [
        ("finding", "Findings"),
        ("decision", "Decisions"),
        ("concepts_under_test", "Concepts under test"),
        ("concepts_other", "Concepts (other)"),
        ("source", "Sources"),
    ]

    for key, header in section_order:
        items = groups.get(key, [])
        if not items:
            continue
        # Sort by updated desc, then id
        items.sort(key=lambda x: (str(x[1].get("updated", "")), str(x[1].get("id", ""))), reverse=True)

        lines.append(f"## {header} ({len(items)})")
        lines.append("")
        for page, fm in items:
            entry_lines = _format_entry(fm)
            lines.extend(entry_lines)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_entry(fm: dict) -> list[str]:
    """Format a single index entry from frontmatter."""
    page_id = fm.get("id", "?")
    status = fm.get("status", "")
    confidence = fm.get("confidence", "")
    summary = str(fm.get("summary", "")).strip()
    relevant_to = fm.get("relevant_to", [])

    # First line: [[id]] · status · confidence
    first_line_parts = [f"[[{page_id}]]"]
    if status:
        first_line_parts.append(status)
    if confidence and fm.get("type") != "source":
        first_line_parts.append(f"{confidence} confidence")
    first_line = "- " + " · ".join(first_line_parts)

    lines = [first_line]
    if summary:
        lines.append(f"  {summary}")
    if relevant_to:
        if isinstance(relevant_to, list) and len(relevant_to) > 0:
            tags = ", ".join(str(t) for t in relevant_to)
            lines.append(f"  _relevant_to:_ {tags}")
    return lines


def check(repo_root: Path, config: dict) -> list[Finding]:
    """Regenerate areas-index.md and all kb/index.md files."""
    findings: list[Finding] = []

    # areas-index.md
    areas_index_path = repo_root / "areas-index.md"
    try:
        content = _generate_areas_index(repo_root)
        _write_if_changed(areas_index_path, content)
    except OSError as e:
        findings.append(
            Finding(RULE_ID, SEVERITY, "areas-index.md", f"could not write: {e}")
        )

    # Per-kb-directory indices
    kb_dirs: set[Path] = set()
    for page in iter_kb_pages(repo_root):
        # Walk up to find the directory whose name is "kb"
        for parent in page.parents:
            if parent.name == "kb":
                kb_dirs.add(parent)
                break
    # Also include kb directories that exist but have no pages (so we write an empty index)
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for kb_dir in parent.rglob("kb"):
            if kb_dir.is_dir():
                kb_dirs.add(kb_dir)

    for kb_dir in sorted(kb_dirs):
        index_path = kb_dir / "index.md"
        try:
            content = _generate_kb_index(kb_dir, repo_root)
            _write_if_changed(index_path, content)
        except OSError as e:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    str(index_path.relative_to(repo_root)),
                    f"could not write index: {e}",
                )
            )

    return findings
