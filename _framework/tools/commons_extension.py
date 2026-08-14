"""
commons_extension — enumerate kb pages in existing areas that might be worth
extending into commons, and apply confirmed extensions.

Triggered from /add-area when ≥1 area already exists. The agent reads candidates,
decides which to surface to the user, the user confirms, and the agent applies
each confirmed extension. The agent decides per-page whether to copy the body
as-is or refine it for general framing.

Two modes:
- `list` (default): enumerate candidates and emit structured JSON to stdout.
- `apply`: given a source page id and (optional) a refined body on stdin,
  write the new commons page, update CHANGELOG, journal the events. Leaves
  the source area page completely unchanged.

Public API:
    list_candidates(repo_root) -> list[Candidate]
    apply_extension(repo_root, source_page_id, refined_body=None) -> ExtensionResult
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from common import (
    VALID_TYPES,
    dump_frontmatter_body,
    find_repo_root,
    iter_kb_pages,
    new_commons_id,
    parse_frontmatter,
)


# Types that are candidates for commons extension. Sources are excluded by
# default — they're typically tied to the area that ingested them.
_DEFAULT_CANDIDATE_TYPES = {"finding", "decision", "concept"}

# Statuses that disqualify a page from being a candidate.
_EXCLUDED_STATUSES = {"superseded", "falsified", "dropped", "archived"}

# Per-type directories inside commons/kb/
_TYPE_DIR = {
    "source": "sources",
    "concept": "concepts",
    "finding": "findings",
    "decision": "decisions",
}


@dataclass
class Candidate:
    """A kb page in an existing area that may be worth extending into commons."""

    page_id: str
    page_type: str
    title: str
    summary: str
    when_to_load: str | None
    relevant_to: list[str]
    status: str
    source_area: str
    source_path: str  # relative to repo root
    body: str  # full body text (after frontmatter)


@dataclass
class ProjectContext:
    """Project-level metadata that helps frame the commons-extension review."""

    area_count: int  # number of existing areas (excluding the new one being added)
    new_area_name: str  # the area triggering this review
    existing_commons_size: int  # count of pages in commons/kb/
    existing_area_kb_size: int  # total kb pages across all existing areas
    candidate_count: int  # candidates returned by list_candidates


@dataclass
class ExtensionResult:
    """Result of applying a single commons extension."""

    source_page_id: str
    new_commons_id: str
    new_commons_path: str  # relative to repo root
    refined: bool  # True if body was changed from source; False if copied as-is


def _new_commons_id(source_page_id: str) -> str:
    """Thin wrapper kept for backward-compatibility within this module's tests."""
    return new_commons_id(source_page_id)


def list_candidates(repo_root: Path, new_area_name: str = "") -> tuple[list[Candidate], ProjectContext]:
    """
    Enumerate kb pages in existing areas that are eligible candidates for
    commons extension.

    A page is eligible if:
    - It's in an area (not already in commons).
    - Its type is finding, decision, or concept (sources excluded by default).
    - Its status is not in the excluded set (superseded/falsified/dropped/archived).
    """
    candidates: list[Candidate] = []
    existing_commons_size = 0
    existing_area_kb_size = 0
    areas_seen: set[str] = set()

    for path in iter_kb_pages(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
        except (OSError, yaml.YAMLError):
            continue

        if not fm:
            continue

        page_type = fm.get("type")
        area = fm.get("area", "")

        # Count for context, regardless of candidate eligibility
        if area == "commons":
            existing_commons_size += 1
            continue
        existing_area_kb_size += 1
        areas_seen.add(area)

        # Apply candidate filters
        if page_type not in _DEFAULT_CANDIDATE_TYPES:
            continue
        if fm.get("status") in _EXCLUDED_STATUSES:
            continue
        if not fm.get("id"):
            continue

        rel_to = fm.get("relevant_to") or []
        if not isinstance(rel_to, list):
            rel_to = []

        candidates.append(
            Candidate(
                page_id=fm["id"],
                page_type=page_type,
                title=fm.get("title", ""),
                summary=fm.get("summary", ""),
                when_to_load=fm.get("when_to_load"),
                relevant_to=[str(t) for t in rel_to],
                status=fm.get("status", ""),
                source_area=area,
                source_path=str(path.relative_to(repo_root)),
                body=body,
            )
        )

    # Don't count the new area itself if it happens to have any kb pages already
    # (it shouldn't, but be defensive)
    if new_area_name in areas_seen:
        areas_seen.discard(new_area_name)

    ctx = ProjectContext(
        area_count=len(areas_seen),
        new_area_name=new_area_name,
        existing_commons_size=existing_commons_size,
        existing_area_kb_size=existing_area_kb_size,
        candidate_count=len(candidates),
    )

    return candidates, ctx


def apply_extension(
    repo_root: Path,
    source_page_id: str,
    new_area_name: str,
    refined_body: str | None = None,
) -> ExtensionResult:
    """
    Create a commons-extended version of an area page.

    The source area page is left completely unchanged. A new page is written
    to commons/kb/<type>/<new-id>.md with frontmatter reflecting promotion
    provenance.

    If refined_body is provided, that's used as the commons page's body.
    Otherwise the source's body is copied verbatim.

    Returns ExtensionResult on success. Raises RuntimeError on failure.
    """
    repo_root = repo_root.resolve()

    # Find the source page by scanning kb pages until id matches
    source_path: Path | None = None
    source_fm: dict | None = None
    source_body: str | None = None
    for path in iter_kb_pages(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
        except (OSError, yaml.YAMLError):
            continue
        if fm and fm.get("id") == source_page_id and fm.get("area") != "commons":
            source_path = path
            source_fm = fm
            source_body = body
            break

    if source_path is None or source_fm is None or source_body is None:
        raise RuntimeError(f"source page not found in any area's kb: {source_page_id}")

    page_type = source_fm.get("type")
    if page_type not in _DEFAULT_CANDIDATE_TYPES:
        raise RuntimeError(f"page type {page_type!r} is not eligible for commons extension")

    new_id = _new_commons_id(source_page_id)
    type_dir = _TYPE_DIR.get(page_type)
    if type_dir is None:
        raise RuntimeError(f"no commons/kb subdirectory for type {page_type!r}")
    target_path = repo_root / "commons" / "kb" / type_dir / f"{new_id}.md"
    if target_path.exists():
        raise RuntimeError(f"commons page already exists at {target_path}")

    # Build the new frontmatter — based on source but with promotion fields
    today = date.today()
    new_fm: dict = {
        "id": new_id,
        "title": source_fm.get("title", ""),
        "type": page_type,
        "status": source_fm.get("status", "active"),
        "area": "commons",
        "created": today,
        "updated": today,
        "summary": source_fm.get("summary", ""),
    }
    # Carry forward type-specific fields verbatim
    for field_name in ("evidence", "provenance", "confidence", "alternatives_considered",
                       "rationale_summary", "superseded_by", "when_to_load"):
        if field_name in source_fm:
            new_fm[field_name] = source_fm[field_name]
    # relevant_to is omitted on commons pages — commons is relevant to everyone
    # by definition (see frontmatter.md). Don't carry it forward.

    # Promotion provenance — distinguishable from /promote's proposal-based path
    new_fm["promoted_from_page"] = source_page_id
    new_fm["promoted_from_area"] = source_fm.get("area", "")
    new_fm["promoted_on"] = today
    new_fm["promotion_path"] = "commons-extension"
    new_fm["promoted_during_add_area"] = new_area_name
    new_fm["human_reviewed"] = True  # user confirmed during interactive review

    # Use refined body if provided, otherwise copy source verbatim
    body_text = refined_body if refined_body is not None else source_body
    refined = refined_body is not None

    # Write the new file
    target_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = _serialize_frontmatter(new_fm) + "\n" + body_text.lstrip("\n")
    target_path.write_text(serialized, encoding="utf-8")

    # Append to commons/CHANGELOG.md
    _append_changelog(repo_root, new_id, page_type, source_page_id,
                      source_fm.get("area", ""), new_area_name)

    return ExtensionResult(
        source_page_id=source_page_id,
        new_commons_id=new_id,
        new_commons_path=str(target_path.relative_to(repo_root)),
        refined=refined,
    )


def _serialize_frontmatter(fm: dict) -> str:
    """Emit YAML frontmatter wrapped in --- delimiters."""
    return "---\n" + dump_frontmatter_body(fm) + "\n---"


def _append_changelog(
    repo_root: Path,
    new_id: str,
    page_type: str,
    source_id: str,
    source_area: str,
    new_area_name: str,
) -> None:
    """Append an entry to commons/CHANGELOG.md."""
    changelog_path = repo_root / "commons" / "CHANGELOG.md"
    today = date.today().isoformat()

    entry = (
        f"\n## {today}\n\n"
        f"- **commons-extension**: extended `{new_id}` ({page_type}) from "
        f"`{source_id}` in `{source_area}/`. Triggered during "
        f"`/add-area {new_area_name}`.\n"
    )

    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        changelog_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
    else:
        header = "# Commons CHANGELOG\n"
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        changelog_path.write_text(header + entry, encoding="utf-8")


# --- CLI ---

def _candidate_to_dict(c: Candidate) -> dict:
    return {
        "page_id": c.page_id,
        "page_type": c.page_type,
        "title": c.title,
        "summary": c.summary,
        "when_to_load": c.when_to_load,
        "relevant_to": c.relevant_to,
        "status": c.status,
        "source_area": c.source_area,
        "source_path": c.source_path,
        "body": c.body,
    }


def _context_to_dict(ctx: ProjectContext) -> dict:
    return {
        "area_count": ctx.area_count,
        "new_area_name": ctx.new_area_name,
        "existing_commons_size": ctx.existing_commons_size,
        "existing_area_kb_size": ctx.existing_area_kb_size,
        "candidate_count": ctx.candidate_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enumerate or apply commons extensions during /add-area."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    list_p = sub.add_parser("list", help="enumerate candidate kb pages")
    list_p.add_argument("--new-area", default="", help="name of the new area being added")
    list_p.add_argument("--repo-root", default=None)

    apply_p = sub.add_parser("apply", help="create a commons extension of a source page")
    apply_p.add_argument("--source-id", required=True, help="id of the area kb page to extend")
    apply_p.add_argument("--new-area", required=True, help="name of the new area being added")
    apply_p.add_argument("--refined-body-file", help="path to a file containing the refined body; if omitted, copy source body verbatim")
    apply_p.add_argument("--repo-root", default=None)

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()

    if args.cmd == "list":
        candidates, ctx = list_candidates(repo_root, args.new_area)
        out = {
            "context": _context_to_dict(ctx),
            "candidates": [_candidate_to_dict(c) for c in candidates],
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.cmd == "apply":
        refined_body = None
        if args.refined_body_file:
            refined_body = Path(args.refined_body_file).read_text(encoding="utf-8")
        try:
            result = apply_extension(
                repo_root, args.source_id, args.new_area, refined_body=refined_body
            )
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps({
            "source_page_id": result.source_page_id,
            "new_commons_id": result.new_commons_id,
            "new_commons_path": result.new_commons_path,
            "refined": result.refined,
        }, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
