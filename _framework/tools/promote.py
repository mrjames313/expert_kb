"""
Promote a proposed page into commons/kb/.

Reads `commons/_proposed/<slug>/page.md`, updates frontmatter (human_reviewed,
promoted_from, promoted_on), moves to `commons/kb/<type>/<id>.md`, and writes
a CHANGELOG entry.

The proposal directory in `_proposed/` is **not deleted** — it stays as audit
trail (proposal.md and any verdict files remain). Only `page.md` moves.

Public API:
    promote(slug, repo_root) -> PromoteResult
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from common import (  # noqa: E402
    VALID_TYPES,
    dump_frontmatter_body,
    find_repo_root,
    new_commons_id,
    parse_frontmatter,
    set_source_twin,
)


# Where the page.md type maps to in commons/kb/
_TYPE_DIR = {
    "source": "sources",
    "concept": "concepts",
    "finding": "findings",
    "decision": "decisions",
}


@dataclass
class PromoteResult:
    slug: str
    moved_from: str
    moved_to: str
    source_page_id: str  # original id from the area kb (and proposal stage)
    new_commons_id: str  # new id at commons/kb/, generated via new_commons_id()
    page_type: str
    promoted_from_area: str
    changelog_updated: bool
    twin_backpointer_set: bool


class PromoteError(RuntimeError):
    """Raised when a promotion cannot proceed."""


def _read_proposed_page(proposed_dir: Path) -> tuple[dict, str]:
    """Read commons/_proposed/<slug>/page.md. Return (frontmatter, body)."""
    page_path = proposed_dir / "page.md"
    if not page_path.is_file():
        raise PromoteError(f"no page.md in proposal directory: {proposed_dir}")
    try:
        text = page_path.read_text(encoding="utf-8")
    except OSError as e:
        raise PromoteError(f"could not read {page_path}: {e}") from e

    try:
        fm, body = parse_frontmatter(text)
    except yaml.YAMLError as e:
        raise PromoteError(f"malformed frontmatter in {page_path}: {e}") from e

    if fm is None:
        raise PromoteError(f"missing frontmatter in {page_path}")
    return fm, body


def _read_proposal_metadata(proposed_dir: Path) -> dict:
    """Read commons/_proposed/<slug>/proposal.md for metadata (proposing area)."""
    proposal_path = proposed_dir / "proposal.md"
    if not proposal_path.is_file():
        return {}
    try:
        text = proposal_path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
    except (OSError, yaml.YAMLError):
        return {}
    return fm or {}


def _emit_frontmatter(fm: dict) -> str:
    """Serialize a frontmatter dict back to YAML with `---` delimiters."""
    return f"---\n{dump_frontmatter_body(fm)}\n---\n"


def _append_changelog_entry(repo_root: Path, page_id: str, page_type: str, from_area: str) -> bool:
    """Prepend a CHANGELOG entry to commons/CHANGELOG.md. Returns True on success."""
    changelog = repo_root / "commons" / "CHANGELOG.md"

    today = date.today().isoformat()
    entry_lines = [
        f"## {today} — promoted {page_type} [[{page_id}]]",
        "",
        f"From: {from_area}",
        "",
    ]
    entry = "\n".join(entry_lines)

    if changelog.is_file():
        existing = changelog.read_text(encoding="utf-8")
    else:
        existing = "# Commons Changelog\n\n_Append-only record of changes promoted into `commons/kb/`. The most recent entries are at the top._\n\n"

    # Insert the new entry right after the introductory paragraph (before any prior entries)
    # Strategy: find the first `## ` heading; insert before it. If none found, append to end.
    match = re.search(r"^## ", existing, re.MULTILINE)
    if match:
        insertion_point = match.start()
        new_text = existing[:insertion_point] + entry + "\n" + existing[insertion_point:]
    else:
        # Strip any "No promotions yet" placeholder
        new_text = re.sub(r"_No promotions yet\._\s*", "", existing).rstrip() + "\n\n" + entry

    try:
        changelog.write_text(new_text, encoding="utf-8")
        return True
    except OSError:
        return False


def promote(slug: str, repo_root: Path) -> PromoteResult:
    """
    Move a proposal from commons/_proposed/<slug>/ to commons/kb/<type>/<id>.md.

    Updates frontmatter:
      - human_reviewed: false
      - promoted_from: <area>  (from proposal.md if available)
      - promoted_on: <today>
      - area: commons

    Writes a CHANGELOG entry. Does NOT delete the proposal directory — it stays
    as audit trail.
    """
    repo_root = repo_root.resolve()
    proposed_dir = repo_root / "commons" / "_proposed" / slug
    if not proposed_dir.is_dir():
        raise PromoteError(f"no such proposal: {proposed_dir}")

    fm, body = _read_proposed_page(proposed_dir)

    page_type = fm.get("type")
    if page_type not in VALID_TYPES:
        raise PromoteError(f"proposal page has invalid type: {page_type!r}")
    if page_type == "por":
        raise PromoteError("POR pages are not promoted through this skill")

    page_id = fm.get("id")
    if not page_id:
        raise PromoteError("proposal page is missing `id`")

    # Generate the new commons id (distinct from the source area's id, so the
    # source area page can stay in place without an id collision).
    new_id = new_commons_id(page_id)

    # Determine target path under commons/kb/<type>/
    type_dir = _TYPE_DIR.get(page_type)
    if type_dir is None:
        raise PromoteError(f"no commons/kb subdir for type {page_type!r}")
    target_path = repo_root / "commons" / "kb" / type_dir / f"{new_id}.md"
    if target_path.exists():
        raise PromoteError(f"target already exists: {target_path}")

    # Determine source area from proposal.md (if available)
    proposal_fm = _read_proposal_metadata(proposed_dir)
    source_area = proposal_fm.get("proposing_area") or fm.get("area") or "unknown"

    # Update frontmatter for promotion. Aligned with commons-extension's shape
    # so both promotion pathways produce consistent frontmatter; differs in
    # `promotion_path` and `human_reviewed` (proposal pathway pages need a
    # reviewer; commons-extension pages were user-confirmed inline).
    today = date.today()
    fm["id"] = new_id
    fm["area"] = "commons"
    fm["human_reviewed"] = False
    fm["promoted_from_page"] = page_id  # original source id
    fm["promoted_from_area"] = source_area
    fm["promoted_on"] = today
    fm["promotion_path"] = "proposal-and-promote"
    fm["updated"] = today
    fm["aligned_on"] = today  # last reconciled with the source (drift detection)
    # relevant_to is omitted on commons pages — commons is relevant to everyone
    # by definition (see frontmatter.md).
    fm.pop("relevant_to", None)

    # Write the new file
    target_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = _emit_frontmatter(fm) + "\n" + body.lstrip("\n")
    target_path.write_text(serialized, encoding="utf-8")

    # Add the commons_twin back-pointer to the source area page (a sanctioned
    # cross-area metadata write). Non-fatal if the source can't be located.
    area_path = source_area if source_area.startswith("areas/") else f"areas/{source_area}"
    src_page = repo_root / area_path / "kb" / type_dir / f"{page_id}.md"
    twin_set = set_source_twin(src_page, new_id)

    # Remove the original page.md from _proposed (other files in the dir stay)
    page_md = proposed_dir / "page.md"
    try:
        page_md.unlink()
    except OSError as e:
        # If we can't remove the source, the target still exists — that's OK
        # but should be reported.
        raise PromoteError(f"copied page but could not remove source: {e}") from e

    # Append to CHANGELOG (uses the new commons id, not the source id)
    changelog_ok = _append_changelog_entry(repo_root, new_id, page_type, source_area)

    return PromoteResult(
        slug=slug,
        moved_from=str(page_md.relative_to(repo_root)),
        moved_to=str(target_path.relative_to(repo_root)),
        source_page_id=page_id,
        new_commons_id=new_id,
        page_type=page_type,
        promoted_from_area=source_area,
        changelog_updated=changelog_ok,
        twin_backpointer_set=twin_set,
    )


# --- CLI ---

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote a proposed page from commons/_proposed/ to commons/kb/."
    )
    parser.add_argument("slug", help="proposal directory name under commons/_proposed/")
    parser.add_argument("--repo", type=Path, default=None)
    args = parser.parse_args()

    try:
        repo_root = args.repo.resolve() if args.repo else find_repo_root()
    except RuntimeError as e:
        print(f"promote: {e}", file=sys.stderr)
        return 2

    try:
        result = promote(args.slug, repo_root)
    except PromoteError as e:
        print(f"promote: {e}", file=sys.stderr)
        return 1

    print(f"Promoted {result.page_type} from [[{result.source_page_id}]] → [[{result.new_commons_id}]]")
    print(f"  from: {result.moved_from}")
    print(f"  to:   {result.moved_to}")
    print(f"  source area: {result.promoted_from_area}")
    if result.changelog_updated:
        print(f"  changelog: updated")
    else:
        print(f"  changelog: WARNING — could not update")
    if result.twin_backpointer_set:
        print(f"  source twin: back-pointer set on [[{result.source_page_id}]]")
    else:
        print(f"  source twin: WARNING — source page not found; commons_twin not set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
