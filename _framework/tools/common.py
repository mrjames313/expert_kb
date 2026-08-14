"""
Shared utilities for lint rules and other framework tools.

Provides:
- Finding dataclass — the unit of lint output
- Frontmatter parsing (YAML between leading and trailing ---)
- File discovery helpers (kb pages, manifests, role files, raw files)
- Repo-root detection
- Constants (valid types, valid statuses per type, etc.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

# --- Constants describing the framework's data model ---

VALID_TYPES = {"source", "concept", "finding", "decision", "por"}

VALID_STATUSES_BY_TYPE = {
    "source": {"active", "archived", "superseded"},
    "concept": {"seed", "developing", "under_test", "supported", "falsified", "dropped", "superseded"},
    "finding": {"active", "archived", "superseded"},
    "decision": {"active", "superseded"},
    "por": {"active"},
}

REQUIRED_FIELDS_ALL = {"id", "title", "type", "status", "area", "created", "updated", "summary"}

ID_PREFIX_BY_TYPE = {
    "source": "s-",
    "concept": "c-",
    "finding": "f-",
    "decision": "d-",
    "por": None,  # POR files don't have id prefix convention
}


# --- Finding type ---

@dataclass
class Finding:
    """One result from a lint rule."""
    rule_id: str  # e.g., "rule_01"
    severity: str  # "error" or "warning"
    file_path: str  # path relative to repo root
    message: str
    line: int | None = None  # 1-indexed; None if not applicable
    suggestion: str | None = None

    def format(self, *, color: bool = False) -> str:
        """Format as a human-readable line."""
        sev = self.severity.upper()
        if color:
            sev_colored = f"\033[31m{sev}\033[0m" if self.severity == "error" else f"\033[33m{sev}\033[0m"
        else:
            sev_colored = sev

        loc = self.file_path
        if self.line is not None:
            loc = f"{loc}:{self.line}"

        lines = [f"{sev_colored:5}  {self.rule_id}  {loc}", f"       {self.message}"]
        if self.suggestion:
            lines.append(f"       suggestion: {self.suggestion}")
        return "\n".join(lines)


# --- Repo navigation ---

def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) until we find _framework/. Raise if not found."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "_framework").is_dir():
            return candidate
    raise RuntimeError(
        f"could not find _framework/ in {here} or any parent — not a expert_kb workspace"
    )


def load_config(repo_root: Path) -> dict:
    """Load _framework/config.yml. Returns parsed dict."""
    config_path = repo_root / "_framework" / "config.yml"
    if not config_path.is_file():
        raise RuntimeError(f"missing config: {config_path}")
    with config_path.open() as f:
        return yaml.safe_load(f) or {}


# --- Frontmatter parsing ---

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """
    Extract YAML frontmatter from the start of a markdown document.

    Returns (frontmatter_dict, body). If no frontmatter, returns (None, text).
    If frontmatter is malformed YAML, or if the file contains a duplicate
    frontmatter block (two `---`-delimited blocks at the top), raises yaml.YAMLError.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    fm_text = m.group(1)
    body = text[m.end():]

    # Detect the duplicate-frontmatter pattern: the first `---`...`---` block
    # parses cleanly, but the body that follows starts with more YAML-key-like
    # lines and then another `---` delimiter. That means the author accidentally
    # produced two frontmatter blocks; the second one is silently lost as
    # body content.
    _check_no_duplicate_frontmatter(body)

    fm = yaml.safe_load(fm_text)
    if not isinstance(fm, dict):
        raise yaml.YAMLError(f"frontmatter must be a mapping, got {type(fm).__name__}")
    return fm, body


_YAML_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*\s*:")


def _check_no_duplicate_frontmatter(body: str) -> None:
    """
    Raise yaml.YAMLError if `body` (the content after a first frontmatter block)
    starts with what looks like a second frontmatter block: 2+ consecutive
    YAML-key-shaped lines followed by a `---` delimiter, all near the top.
    """
    lines = body.split("\n", 30)[:30]
    # Skip leading blanks
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    yaml_like = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "":
            i += 1
            continue
        if stripped == "---":
            if yaml_like >= 2:
                raise yaml.YAMLError(
                    "duplicate frontmatter: the file contains two `---`-delimited "
                    "blocks at the top. Markdown files may have at most one "
                    "frontmatter block. Merge into a single block bounded by "
                    "exactly one pair of `---` delimiters."
                )
            return  # `---` reached, but no duplicate pattern; done
        if _YAML_KEY_RE.match(stripped):
            yaml_like += 1
            i += 1
            continue
        # Anything else (prose, heading, etc.) — not a duplicate-frontmatter pattern
        return


def read_page(path: Path) -> tuple[dict | None, str, list[str]]:
    """
    Read a markdown file. Returns (frontmatter, body, lines) where lines is the
    full file split for line-number reporting.

    Raises on file-not-found or YAML errors.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fm, body = parse_frontmatter(text)
    return fm, body, lines


# --- File discovery ---

def iter_kb_pages(repo_root: Path) -> Iterator[Path]:
    """Yield all .md files under any kb/ directory in commons or areas."""
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for path in parent.rglob("kb/**/*.md"):
            if path.is_file() and path.name != "index.md":
                yield path


def iter_role_files(repo_root: Path) -> Iterator[Path]:
    """Yield all role.md files under any roles/ directory."""
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for path in parent.rglob("roles/**/role.md"):
            if path.is_file():
                yield path


def iter_pulse_files(repo_root: Path) -> Iterator[Path]:
    """Yield all pulse.md files (commons and per-area)."""
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for path in parent.rglob("pulse.md"):
            if path.is_file():
                yield path


def iter_manifest_files(repo_root: Path) -> Iterator[Path]:
    """Yield all data manifest files under data/manifests/."""
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for path in parent.rglob("data/manifests/*.md"):
            if path.is_file():
                yield path


def iter_spec_files(repo_root: Path) -> Iterator[Path]:
    """
    Yield spec planning files: brief.md, plan.md, tasks.md, outcome.md
    under any spec directory at areas/<area>/specs/<spec>/.

    These are prose files where frontmatter is OPTIONAL. They get lighter
    lint treatment than kb pages (only well-formedness is checked, not
    required fields).
    """
    areas_root = repo_root / "areas"
    if not areas_root.is_dir():
        return
    for specs_dir in areas_root.rglob("specs"):
        if not specs_dir.is_dir():
            continue
        for spec_dir in specs_dir.iterdir():
            if not spec_dir.is_dir():
                continue
            for name in ("brief.md", "plan.md", "tasks.md", "outcome.md"):
                path = spec_dir / name
                if path.is_file():
                    yield path


def iter_raw_files(repo_root: Path) -> Iterator[Path]:
    """Yield all files under any raw/ directory."""
    for parent in [repo_root / "commons", repo_root / "areas"]:
        if not parent.is_dir():
            continue
        for raw_dir in parent.rglob("raw"):
            if not raw_dir.is_dir():
                continue
            for path in raw_dir.rglob("*"):
                if path.is_file() and not path.name.startswith(".git"):
                    yield path


def iter_areas(repo_root: Path) -> Iterator[Path]:
    """Yield each area directory (including sub-areas) under areas/."""
    areas_root = repo_root / "areas"
    if not areas_root.is_dir():
        return
    for path in areas_root.rglob("brief.md"):
        yield path.parent


# --- ID convention check ---

_ID_RE = re.compile(r"^[scfd]-\d{4}-\d{2}(?:-\d{2})?-[a-z0-9-]+$")
# Alternate form for pages promoted to commons via commons-extension:
# the date segment is replaced with the literal "commons".
_ID_COMMONS_RE = re.compile(r"^[scfd]-commons-[a-z0-9-]+$")


def new_commons_id(source_page_id: str) -> str:
    """
    Generate a commons-pathway id from a source area page id.

    Convention: replace the date segment with the literal `commons`.
        f-2026-05-26-accredited-investor-... → f-commons-accredited-investor-...

    Used by both promotion pathways:
    - commons_extension.py (commons-extension at /add-area time)
    - promote.py (proposal-and-promote flow)

    The point of the convention: the new commons page gets a distinct id from
    the source area page (which stays in place), preventing id collisions.
    """
    parts = source_page_id.split("-")
    if len(parts) < 4:
        # Falls outside the expected convention; prefix safely with commons-
        return f"{parts[0]}-commons-{'-'.join(parts[1:])}"

    type_prefix = parts[0]
    # Skip the date segments (YYYY, MM, optional DD)
    idx = 1
    if len(parts[idx]) == 4 and parts[idx].isdigit():
        idx += 1
        if idx < len(parts) and len(parts[idx]) == 2 and parts[idx].isdigit():
            idx += 1
            if idx < len(parts) and len(parts[idx]) == 2 and parts[idx].isdigit():
                idx += 1

    slug = "-".join(parts[idx:])
    if not slug:
        return f"{type_prefix}-commons"
    return f"{type_prefix}-commons-{slug}"


def is_valid_id(page_id: str, page_type: str) -> bool:
    """
    Check that an id matches one of the accepted conventions:
    - <prefix>-YYYY-MM[-DD]-<slug>  (default, for area kb pages and
      proposal-pathway promotions that preserve the source id)
    - <prefix>-commons-<slug>  (commons-extension pathway: dateless,
      generated by commons_extension.py during /add-area)
    """
    if page_type == "por":
        return True  # POR doesn't use the id convention
    prefix = ID_PREFIX_BY_TYPE.get(page_type)
    if prefix is None:
        return True
    if not page_id.startswith(prefix):
        return False
    return bool(_ID_RE.match(page_id) or _ID_COMMONS_RE.match(page_id))


# --- Wikilink extraction ---

# Matches [[target]] or [[target|alias]]. Captures `target`.
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def extract_wikilinks(text: str) -> list[str]:
    """Return all wikilink targets (no alias, no extension) from markdown text."""
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(text)]


def split_wikilink(raw: str) -> tuple[str | None, str]:
    """Split an optional ``area:`` prefix from a wikilink target.

    Splits on the first colon only, so a nested prefix like ``research/optics``
    and a slash-bearing target like ``concepts/c-foo`` both survive intact.
    Returns ``(area_prefix_or_None, target)``.
    """
    if ":" in raw:
        prefix, target = raw.split(":", 1)
        return prefix.strip(), target.strip()
    return None, raw.strip()


def page_area(page: Path, repo_root: Path) -> str | None:
    """The area a kb page belongs to, as it appears in a wikilink prefix.

    ``"commons"``, a leaf area like ``"engineering"``, or a nested area like
    ``"research/optics"``. Returns None if the path isn't under a ``kb/`` dir.
    """
    parts = page.relative_to(repo_root).parts
    if "kb" not in parts:
        return None
    kb_idx = parts.index("kb")
    if parts[0] == "commons":
        return "commons"
    if parts[0] == "areas":
        return "/".join(parts[1:kb_idx])
    return None


def build_wikilink_index(repo_root: Path) -> dict[str, Path]:
    """Map every wikilink target to its resolving kb page, across commons and
    all areas.

    Keyed by within-kb path (e.g. ``concepts/c-foo``) and by bare id (the
    filename stem). Area prefixes are not part of the key — strip them with
    :func:`split_wikilink` before lookup.
    """
    index: dict[str, Path] = {}
    for page in iter_kb_pages(repo_root):
        parts = page.relative_to(repo_root).parts
        if "kb" not in parts:
            continue
        kb_idx = parts.index("kb")
        within_kb = "/".join(parts[kb_idx + 1:])
        target_with_dir = within_kb[:-3] if within_kb.endswith(".md") else within_kb
        index[target_with_dir] = page
        index.setdefault(page.stem, page)
    return index
