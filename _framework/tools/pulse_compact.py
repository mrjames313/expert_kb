"""
Compact pulse — materialize pulse.log events into pulse.md, then truncate the log.

For each area (and commons) with a _journal/pulse.log:

1. Read the log and parse entries.
2. Verify any '→ to be filed:' references resolve to existing kb pages
   (warn if not — the agent should have created the page during the session).
3. Update pulse.md:
   - Preserved sections: "Current focus" and "Open questions". Current focus
     gets overwritten by the most recent focus-shift entry. Open questions are
     extended by new `question` entries and pruned by `question-closed` entries
     (which name the questions they retire via `→ closes:` directives).
   - Regenerated sections: "Recent decisions", "Active concepts under test",
     "Recent findings" — rebuilt from the current kb state, scoped to the area.
4. Verify the compacted pulse.md is under the line cap.
5. Truncate the pulse.log.

Idempotent: running compact twice in a row with no log entries between is a no-op.

Public API:
    compact_area(area_dir, repo_root, config) -> CompactResult
    compact_all(repo_root, config) -> dict[area_path, CompactResult]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from activity_days import active_days_back  # noqa: E402
from common import (  # noqa: E402
    find_repo_root,
    iter_areas,
    load_config,
    parse_frontmatter,
)


# --- Log entry parsing ---

_LOG_HEADING_RE = re.compile(
    r"^##\s+\[(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s+(?P<event>\S+)(?:\s+(?P<role>.+))?$"
)
_FILED_RE = re.compile(r"^→\s+to be filed:\s+(?P<path>\S+)\s*$")
_CLOSES_RE = re.compile(r"^→\s+closes:\s+(?P<text>.+?)\s*$")

# A `→ to be filed:` path is documented as kb-relative (e.g. `findings/f-…`),
# but agents naturally write the repo-root form (`areas/<area>/kb/findings/f-…`
# or `commons/kb/findings/f-…`). Strip a leading area/commons kb prefix so both
# forms resolve against kb_dir and neither produces a spurious "not found"
# warning. kb-relative paths (findings/, decisions/, concepts/, sources/) never
# contain `kb/`, so this cannot mangle a correctly-formed path.
_KB_PREFIX_RE = re.compile(r"^(?:areas/[^/]+/kb/|commons/kb/)")


def normalize_filed_path(filed_path: str) -> str:
    """Reduce a `→ to be filed:` path to its kb-relative form."""
    return _KB_PREFIX_RE.sub("", filed_path)


@dataclass
class LogEntry:
    timestamp: str  # "YYYY-MM-DD HH:MM"
    event_type: str  # decision | finding | concept | focus-shift | question | question-closed
    role: str | None
    description: str  # everything between the heading and any → directives
    filed_path: str | None  # e.g., "decisions/d-2026-05-04-bias-current"
    closes_questions: list[str] = field(default_factory=list)  # for question-closed entries


def parse_pulse_log(log_text: str) -> list[LogEntry]:
    """Parse a pulse.log file into entries. Skip malformed sections rather than fail."""
    entries: list[LogEntry] = []
    current: LogEntry | None = None
    description_lines: list[str] = []

    def flush() -> None:
        if current is not None:
            current.description = "\n".join(description_lines).strip()
            entries.append(current)

    for raw_line in log_text.splitlines():
        line = raw_line.rstrip()
        m = _LOG_HEADING_RE.match(line)
        if m:
            flush()
            current = LogEntry(
                timestamp=m.group("ts"),
                event_type=m.group("event").strip(),
                role=(m.group("role") or "").strip() or None,
                description="",
                filed_path=None,
            )
            description_lines = []
            continue

        if current is None:
            continue

        filed_match = _FILED_RE.match(line)
        if filed_match:
            current.filed_path = filed_match.group("path").strip()
            continue

        closes_match = _CLOSES_RE.match(line)
        if closes_match:
            current.closes_questions.append(closes_match.group("text").strip())
            continue

        description_lines.append(line)

    flush()
    return entries


# --- pulse.md section parsing ---

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def split_sections(md_text: str) -> dict[str, list[str]]:
    """
    Split pulse.md content into sections by H2 heading.
    Returns {section_name: list_of_lines}.

    Lines before the first H2 are stored under key "".
    Section names are normalized: lowercased, parenthetical detail stripped.
    The full original heading line is kept as the first line of the section.
    """
    sections: dict[str, list[str]] = {"": []}
    current_key = ""
    for line in md_text.splitlines():
        m = _SECTION_HEADING_RE.match(line)
        if m:
            heading = m.group(1).strip()
            # Normalize: drop parenthetical, lowercase
            key = re.sub(r"\s*\(.*?\)\s*$", "", heading).strip().lower()
            current_key = key
            sections.setdefault(current_key, [])
            sections[current_key].append(line)
        else:
            sections.setdefault(current_key, []).append(line)
    return sections


# --- Querying kb state for regeneration ---

@dataclass
class KbEntry:
    """Lightweight kb-page record for pulse regeneration."""
    page_id: str
    title: str
    summary: str
    status: str
    type: str
    updated: str  # ISO date
    path: Path
    confidence: str | None = None


def scan_kb(kb_dir: Path) -> list[KbEntry]:
    """Walk a kb/ directory, return KbEntry for every page (excluding index.md)."""
    entries: list[KbEntry] = []
    if not kb_dir.is_dir():
        return entries
    for md in kb_dir.rglob("*.md"):
        if md.name == "index.md":
            continue
        try:
            fm, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not fm:
            continue
        entries.append(KbEntry(
            page_id=str(fm.get("id", md.stem)),
            title=str(fm.get("title", "")),
            summary=str(fm.get("summary", "")),
            status=str(fm.get("status", "")),
            type=str(fm.get("type", "")),
            updated=str(fm.get("updated", "")),
            path=md,
            confidence=str(fm["confidence"]) if "confidence" in fm else None,
        ))
    return entries


def filter_recent_by_active_days(
    entries: list[KbEntry],
    days_back: int,
    repo_root: Path,
) -> list[KbEntry]:
    """Filter to entries whose `updated` is on or after `days_back` active days ago."""
    cutoff_date = active_days_back(days_back, repo_root=repo_root)
    if cutoff_date is None:
        return entries  # not enough history; keep everything
    cutoff_iso = cutoff_date.isoformat()
    return [e for e in entries if e.updated and e.updated >= cutoff_iso]


# --- First-sentence extraction ---

# Abbreviations whose trailing period must NOT be treated as a sentence end.
# Each entry keeps a **leading space** so it only matches as a whole word, not
# as the suffix of a longer word — otherwise " no." would fire inside "casino."
# and " ca." inside "Rebecca." Matched case-insensitively; an abbreviation at
# the very start of the text is matched too. Grow this list as new false-split
# cases surface (keep the leading space).
SENTENCE_ABBREVIATIONS = [
    " e.g.",
    " i.e.",
    " etc.",
    " vs.",
    " et al.",
    " cf.",
    " approx.",
    " resp.",
    " ca.",
    " fig.",
    " eq.",
    " sec.",
    " app.",
    " tab.",
    " no.",
    " Dr.",
    " Mr.",
    " Mrs.",
    " Ph.D.",
    " U.S.",
]

# A sentence terminator is . ! or ? followed by whitespace or end of string.
# The lookahead keeps decimals like "v3.5" (period followed by a digit) from
# counting as a break.
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")

# A single-letter initial ("W" in "Fitted by W. Gurnee") right before the
# terminator: a lone letter preceded by whitespace or start-of-string. Kept out
# of the abbreviation list because it can't be enumerated letter by letter.
_INITIAL = re.compile(r"(?:^|\s)[A-Za-z]\Z")


def first_sentence(text: str) -> str:
    """Return the first sentence of `text`, trailing terminator stripped; the
    whole (stripped) string if there is no sentence break.

    A period ends a sentence only when followed by whitespace or end of string,
    so decimals such as "v3.5" don't split. A candidate terminator is skipped
    when it closes a known abbreviation (SENTENCE_ABBREVIATIONS) or a
    single-letter initial — in both cases matched as a whole token."""
    text = text.strip()
    lowered = text.lower()
    abbrevs = [a.lower() for a in SENTENCE_ABBREVIATIONS]
    for match in _SENTENCE_END.finditer(text):
        prefix = lowered[: match.start() + 1]  # up to and including the terminator
        before = text[: match.start()]         # up to (not including) the terminator
        # Known abbreviation ending here (whole word: leading space, or at start)?
        if any(prefix.endswith(a) or prefix == a.lstrip() for a in abbrevs):
            continue
        # Single-letter initial ending here?
        if _INITIAL.search(before):
            continue
        return text[: match.start()]
    return text


# --- Section regenerators ---

def regenerate_recent_decisions(
    kb_entries: list[KbEntry], repo_root: Path, days_back: int
) -> list[str]:
    """Build the body of the "Recent decisions" section."""
    decisions = [e for e in kb_entries if e.type == "decision" and e.status == "active"]
    recent = filter_recent_by_active_days(decisions, days_back, repo_root)
    recent.sort(key=lambda e: e.updated, reverse=True)
    lines = [f"## Recent decisions (last {days_back} active days)", ""]
    if not recent:
        lines.append("_None._")
    else:
        for e in recent:
            summary = first_sentence(e.summary) if e.summary else e.title
            lines.append(f"- [[{e.page_id}]] — {summary}")
    lines.append("")
    return lines


def regenerate_concepts_under_test(kb_entries: list[KbEntry]) -> list[str]:
    """Build the body of the "Active concepts under test" section."""
    concepts = [e for e in kb_entries if e.type == "concept" and e.status == "under_test"]
    concepts.sort(key=lambda e: e.updated, reverse=True)
    lines = ["## Active concepts under test", ""]
    if not concepts:
        lines.append("_None._")
    else:
        for e in concepts:
            conf = f" · {e.confidence} confidence" if e.confidence else ""
            summary = first_sentence(e.summary) if e.summary else e.title
            lines.append(f"- [[{e.page_id}]]{conf} — {summary}")
    lines.append("")
    return lines


def regenerate_recent_findings(kb_entries: list[KbEntry], max_count: int = 5) -> list[str]:
    """Build the body of the "Recent findings" section."""
    findings = [e for e in kb_entries if e.type == "finding" and e.status == "active"]
    findings.sort(key=lambda e: e.updated, reverse=True)
    findings = findings[:max_count]
    lines = [f"## Recent findings (last {max_count})", ""]
    if not findings:
        lines.append("_None._")
    else:
        for e in findings:
            summary = first_sentence(e.summary) if e.summary else e.title
            lines.append(f"- [[{e.page_id}]] — {summary}")
    lines.append("")
    return lines


# --- Applying log entries to preserved sections ---

def update_current_focus(existing_section: list[str], log_entries: list[LogEntry]) -> list[str]:
    """
    If any focus-shift entries exist in the log, the most recent one replaces
    the body of "Current focus". Otherwise leave the section as-is.
    """
    focus_shifts = [e for e in log_entries if e.event_type == "focus-shift"]
    if not focus_shifts:
        return existing_section
    latest = focus_shifts[-1]
    description = latest.description.strip() or "_(set by recent focus-shift)_"
    return ["## Current focus", "", description, ""]


def _normalize_question(text: str) -> str:
    """Normalize question text for matching: lowercase, collapse whitespace, strip terminal punctuation."""
    text = " ".join(text.lower().split())
    return text.rstrip(".?!")


def update_open_questions(existing_section: list[str], log_entries: list[LogEntry]) -> list[str]:
    """
    Update the "Open questions" section:
    - Add new questions from `question` log entries (deduplicated).
    - Remove questions matching any `→ closes:` directive in `question-closed` entries.

    Matching is done on normalized text (lowercase, collapsed whitespace,
    stripped terminal punctuation) so minor formatting differences don't break it.
    """
    existing_questions: list[str] = []
    capture = False
    for line in existing_section:
        if line.startswith("##"):
            capture = True
            continue
        if not capture:
            continue
        if line.strip().startswith("-"):
            existing_questions.append(line.strip()[1:].strip())

    # Build the set of normalized targets to close
    closes_targets: set[str] = set()
    for e in log_entries:
        if e.event_type == "question-closed":
            for target in e.closes_questions:
                closes_targets.add(_normalize_question(target))

    # Apply closures to existing questions
    existing_questions = [
        q for q in existing_questions if _normalize_question(q) not in closes_targets
    ]

    # Add new questions from log, dedup against current set + closes targets
    current_norm = {_normalize_question(q) for q in existing_questions}
    for e in log_entries:
        if e.event_type == "question":
            # Collapse to one line so multi-line question bodies round-trip
            # through pulse.md — the re-parser only reads "-" lines, so an
            # embedded newline would drop everything after the first line and
            # make the question unclosable by its original wording.
            q = " ".join(e.description.split())
            qn = _normalize_question(q)
            if not q or qn in current_norm or qn in closes_targets:
                continue
            existing_questions.append(q)
            current_norm.add(qn)

    lines = ["## Open questions", ""]
    if not existing_questions:
        lines.append("_None yet._")
    else:
        for q in existing_questions:
            lines.append(f"- {q}")
    lines.append("")
    return lines


# --- Compaction ---

@dataclass
class CompactResult:
    area_path: str
    entries_compacted: int
    missing_filed_paths: list[str] = field(default_factory=list)
    out_of_order: list[str] = field(default_factory=list)
    pulse_line_count: int = 0
    over_cap: bool = False
    cap: int = 0
    truncated_log: bool = False


def _identify_kb_dir(area_dir: Path) -> Path:
    return area_dir / "kb"


def _identify_pulse_md(area_dir: Path) -> Path:
    return area_dir / "pulse.md"


def _identify_pulse_log(area_dir: Path) -> Path:
    return area_dir / "_journal" / "pulse.log"


def compact_area(area_dir: Path, repo_root: Path, config: dict) -> CompactResult:
    """
    Compact one area (or commons). area_dir is the directory containing pulse.md.

    Idempotent — running with an empty log is a no-op.
    """
    area_dir = area_dir.resolve()
    repo_root = repo_root.resolve()

    pulse_md = _identify_pulse_md(area_dir)
    pulse_log = _identify_pulse_log(area_dir)
    kb_dir = _identify_kb_dir(area_dir)

    try:
        rel_area = str(area_dir.relative_to(repo_root))
    except ValueError:
        rel_area = str(area_dir)

    result = CompactResult(area_path=rel_area, entries_compacted=0)

    if not pulse_md.is_file():
        # Nothing to compact; not an error
        return result

    # Parse log if present
    log_entries: list[LogEntry] = []
    if pulse_log.is_file():
        log_text = pulse_log.read_text(encoding="utf-8")
        log_entries = parse_pulse_log(log_text)
        result.entries_compacted = len(log_entries)

    # Verify chronological order. pulse.log is append-only, so timestamps should
    # be non-decreasing top-to-bottom. A strict decrease means an entry landed
    # out of order — usually an agent prepending instead of appending. Timestamps
    # are zero-padded "YYYY-MM-DD HH:MM", so a string compare is chronological.
    prev = None
    for entry in log_entries:
        if prev is not None and entry.timestamp < prev:
            result.out_of_order.append(
                f"{entry.timestamp} appears after {prev} (entries should be appended, not prepended)"
            )
        prev = entry.timestamp

    # Verify filed paths
    for entry in log_entries:
        if entry.filed_path:
            # filed_path is documented as kb-relative (e.g., "decisions/d-..."),
            # but tolerate the repo-root form (areas/<area>/kb/... or commons/kb/...).
            rel = normalize_filed_path(entry.filed_path)
            candidate = kb_dir / f"{rel}.md" if not rel.endswith(".md") else kb_dir / rel
            if not candidate.is_file():
                result.missing_filed_paths.append(entry.filed_path)

    # Scan kb to drive regenerated sections
    kb_entries = scan_kb(kb_dir)

    # Load and split current pulse.md
    pulse_text = pulse_md.read_text(encoding="utf-8")
    sections = split_sections(pulse_text)

    lint_cfg = config.get("lint", {}) if isinstance(config, dict) else {}
    days_back = int(lint_cfg.get("recent_decisions_window_active_days", 7))
    line_cap = int(lint_cfg.get("pulse_line_cap", 80))
    result.cap = line_cap

    # Build the new pulse.md from sections in canonical order
    new_lines: list[str] = []

    # Preamble (everything before the first section)
    preamble = sections.get("", [])
    if preamble:
        new_lines.extend(preamble)
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
    else:
        # If there's no preamble, drop in a basic title
        title = f"# {rel_area} — pulse" if rel_area != "commons" else "# Commons — pulse"
        new_lines.extend([title, ""])

    # 1) Current focus (preserved, optionally updated from log)
    current_focus_existing = sections.get("current focus", ["## Current focus", "", "_(set when work begins)_", ""])
    new_lines.extend(update_current_focus(current_focus_existing, log_entries))

    # 2) Recent decisions (regenerated)
    new_lines.extend(regenerate_recent_decisions(kb_entries, repo_root, days_back))

    # 3) Active concepts under test (regenerated)
    new_lines.extend(regenerate_concepts_under_test(kb_entries))

    # 4) Open questions (preserved + updates from log)
    open_q_existing = sections.get("open questions", ["## Open questions", "", "_None yet._", ""])
    new_lines.extend(update_open_questions(open_q_existing, log_entries))

    # 5) Recent findings (regenerated)
    new_lines.extend(regenerate_recent_findings(kb_entries))

    # Write back, normalizing trailing whitespace
    new_text = "\n".join(line.rstrip() for line in new_lines).rstrip() + "\n"
    pulse_md.write_text(new_text, encoding="utf-8")

    result.pulse_line_count = len(new_text.splitlines())
    result.over_cap = result.pulse_line_count > line_cap

    # Truncate the log only if we successfully wrote pulse.md
    if pulse_log.is_file():
        pulse_log.write_text("", encoding="utf-8")
        result.truncated_log = True

    return result


def compact_all(repo_root: Path, config: dict) -> dict[str, CompactResult]:
    """Compact commons and every area. Returns map keyed by area path."""
    results: dict[str, CompactResult] = {}
    commons = repo_root / "commons"
    if (commons / "pulse.md").is_file():
        results["commons"] = compact_area(commons, repo_root, config)
    for area_dir in iter_areas(repo_root):
        rel = str(area_dir.relative_to(repo_root))
        results[rel] = compact_area(area_dir, repo_root, config)
    return results


# --- CLI ---

def main() -> int:
    parser = argparse.ArgumentParser(description="Compact pulse.log into pulse.md.")
    parser.add_argument(
        "area",
        nargs="?",
        help="path to area directory to compact (default: all areas + commons)",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="path to repo root (default: auto-detect from cwd)",
    )
    args = parser.parse_args()

    try:
        repo_root = args.repo.resolve() if args.repo else find_repo_root()
    except RuntimeError as e:
        print(f"pulse_compact: {e}", file=sys.stderr)
        return 2

    try:
        config = load_config(repo_root)
    except RuntimeError as e:
        print(f"pulse_compact: {e}", file=sys.stderr)
        return 2

    if args.area:
        area_dir = Path(args.area).resolve()
        result = compact_area(area_dir, repo_root, config)
        _print_result(result)
        return 0 if not result.over_cap else 1

    results = compact_all(repo_root, config)
    if not results:
        print("pulse_compact: no pulse files found.")
        return 0
    any_over_cap = False
    for area, result in results.items():
        _print_result(result)
        any_over_cap = any_over_cap or result.over_cap
    return 0 if not any_over_cap else 1


def _print_result(result: CompactResult) -> None:
    status = "OK" if not result.over_cap else f"OVER CAP ({result.pulse_line_count}/{result.cap})"
    print(f"{result.area_path}: {result.entries_compacted} entries compacted, "
          f"pulse {result.pulse_line_count} lines [{status}]")
    if result.missing_filed_paths:
        print("  Warning: filed paths from log not found on disk:")
        for p in result.missing_filed_paths:
            print(f"    - {p}")
    if result.out_of_order:
        print("  Warning: pulse.log entries out of chronological order "
              "(append new entries at the bottom, don't prepend):")
        for msg in result.out_of_order:
            print(f"    - {msg}")


if __name__ == "__main__":
    raise SystemExit(main())
