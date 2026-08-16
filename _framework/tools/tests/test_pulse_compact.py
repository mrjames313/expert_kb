"""
Tests for _framework/tools/pulse_compact.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pulse_compact import (
    LogEntry,
    compact_area,
    first_sentence,
    parse_pulse_log,
    split_sections,
    update_current_focus,
    update_open_questions,
)

from lint_helpers import make_minimal_repo, write_kb_page


DEFAULT_CONFIG = {"lint": {"pulse_line_cap": 80, "recent_decisions_window_active_days": 7}}


# --- parse_pulse_log ---

class TestParsePulseLog:
    def test_empty_log(self) -> None:
        assert parse_pulse_log("") == []

    def test_single_decision_entry(self) -> None:
        log = textwrap.dedent("""
            ## [2026-05-08 09:14] decision optics-researcher
            Adopted bias current of 1 mA per measurement constraints.
            → to be filed: decisions/d-2026-05-04-bias-current
        """).strip()
        entries = parse_pulse_log(log)
        assert len(entries) == 1
        assert entries[0].timestamp == "2026-05-08 09:14"
        assert entries[0].event_type == "decision"
        assert entries[0].role == "optics-researcher"
        assert "1 mA" in entries[0].description
        assert entries[0].filed_path == "decisions/d-2026-05-04-bias-current"

    def test_multiple_entries(self) -> None:
        log = textwrap.dedent("""
            ## [2026-05-08 09:14] decision optics-researcher
            First decision.
            → to be filed: decisions/d-1

            ## [2026-05-08 11:22] finding optics-researcher
            First finding.
            → to be filed: findings/f-1

            ## [2026-05-08 13:45] focus-shift optics-researcher
            Switching gears.
        """).strip()
        entries = parse_pulse_log(log)
        assert len(entries) == 3
        assert [e.event_type for e in entries] == ["decision", "finding", "focus-shift"]
        assert entries[2].filed_path is None  # focus-shift has no filed_path

    def test_handles_missing_role(self) -> None:
        log = "## [2026-05-08 09:14] decision\nNo role specified.\n"
        entries = parse_pulse_log(log)
        assert len(entries) == 1
        assert entries[0].role is None


# --- split_sections ---

class TestSplitSections:
    def test_basic_sections(self) -> None:
        text = textwrap.dedent("""
            # Header

            Preamble line.

            ## Current focus

            Some focus text.

            ## Open questions

            - q1
            - q2
        """).strip()
        sections = split_sections(text)
        assert "" in sections  # preamble
        assert "current focus" in sections
        assert "open questions" in sections
        # The preamble holds the title and any pre-section text
        assert any("Header" in line for line in sections[""])

    def test_parenthetical_in_heading_stripped(self) -> None:
        text = "## Recent decisions (last 7 active days)\n- d1\n"
        sections = split_sections(text)
        assert "recent decisions" in sections


# --- update_current_focus ---

class TestUpdateCurrentFocus:
    def test_no_focus_shift_leaves_unchanged(self) -> None:
        existing = ["## Current focus", "", "Previous focus.", ""]
        result = update_current_focus(existing, [])
        assert result == existing

    def test_focus_shift_replaces(self) -> None:
        existing = ["## Current focus", "", "Old focus.", ""]
        log_entries = [
            LogEntry(
                timestamp="2026-05-08 09:00",
                event_type="focus-shift",
                role="r",
                description="New focus on noise floor.",
                filed_path=None,
            )
        ]
        result = update_current_focus(existing, log_entries)
        assert any("New focus on noise floor" in line for line in result)
        assert not any("Old focus" in line for line in result)

    def test_multiple_shifts_latest_wins(self) -> None:
        existing = ["## Current focus", "", "Old.", ""]
        log_entries = [
            LogEntry("2026-05-08 09:00", "focus-shift", "r", "First shift.", None),
            LogEntry("2026-05-08 14:00", "focus-shift", "r", "Latest shift.", None),
        ]
        result = update_current_focus(existing, log_entries)
        assert any("Latest shift" in line for line in result)
        assert not any("First shift" in line for line in result)


# --- update_open_questions ---

class TestUpdateOpenQuestions:
    def test_adds_new_question(self) -> None:
        existing = ["## Open questions", "", "- Existing question?", ""]
        log_entries = [
            LogEntry("2026-05-08 09:00", "question", "r", "New question?", None)
        ]
        result = update_open_questions(existing, log_entries)
        assert any("Existing question?" in line for line in result)
        assert any("New question?" in line for line in result)

    def test_deduplicates(self) -> None:
        existing = ["## Open questions", "", "- Same question?", ""]
        log_entries = [
            LogEntry("2026-05-08 09:00", "question", "r", "Same question?", None)
        ]
        result = update_open_questions(existing, log_entries)
        # Should appear only once
        same_count = sum(1 for line in result if "Same question?" in line)
        assert same_count == 1

    def test_replaces_none_placeholder(self) -> None:
        existing = ["## Open questions", "", "_None yet._", ""]
        log_entries = [
            LogEntry("2026-05-08 09:00", "question", "r", "First question?", None)
        ]
        result = update_open_questions(existing, log_entries)
        assert any("First question?" in line for line in result)
        assert not any("_None yet._" in line for line in result)

    def test_question_closed_removes_existing(self) -> None:
        """A question-closed entry with a → closes: directive removes the matching question."""
        existing = [
            "## Open questions", "",
            "- Does Rule 152 apply here?",
            "- Should we file under 506(d)?",
            "- Something unrelated?",
            "",
        ]
        log_entries = [
            LogEntry(
                "2026-05-08 09:00", "question-closed", "r",
                "Rule 152 confirmed not applicable", None,
                closes_questions=["Does Rule 152 apply here?"],
            ),
        ]
        result = update_open_questions(existing, log_entries)
        assert not any("Rule 152" in line for line in result)
        assert any("506(d)" in line for line in result)  # untouched
        assert any("Something unrelated?" in line for line in result)

    def test_question_closed_matches_case_insensitive_and_punctuation(self) -> None:
        """Closure matching is robust to case and trailing punctuation."""
        existing = ["## Open questions", "", "- Does Rule 152 apply here?", ""]
        log_entries = [
            LogEntry(
                "2026-05-08 09:00", "question-closed", "r", "resolved", None,
                closes_questions=["does rule 152 apply here"],  # different case, no question mark
            ),
        ]
        result = update_open_questions(existing, log_entries)
        assert not any("Rule 152" in line for line in result)

    def test_question_closed_multiple_targets(self) -> None:
        """One question-closed entry can close multiple questions."""
        existing = [
            "## Open questions", "",
            "- Question A?",
            "- Question B?",
            "- Question C?",
            "",
        ]
        log_entries = [
            LogEntry(
                "2026-05-08 09:00", "question-closed", "r", "two resolved at once", None,
                closes_questions=["Question A?", "Question B?"],
            ),
        ]
        result = update_open_questions(existing, log_entries)
        assert not any("Question A?" in line for line in result)
        assert not any("Question B?" in line for line in result)
        assert any("Question C?" in line for line in result)

    def test_question_and_closure_same_session(self) -> None:
        """A question asked AND closed within the same session never appears in pulse.md."""
        existing = ["## Open questions", "", "_None yet._", ""]
        log_entries = [
            LogEntry("2026-05-08 09:00", "question", "r", "Transient question?", None),
            LogEntry(
                "2026-05-08 11:00", "question-closed", "r", "Quickly resolved", None,
                closes_questions=["Transient question?"],
            ),
        ]
        result = update_open_questions(existing, log_entries)
        assert not any("Transient question?" in line for line in result)

    def test_closure_with_no_matching_question_is_noop(self) -> None:
        """A closes directive targeting nothing in pulse.md silently passes."""
        existing = ["## Open questions", "", "- Real question?", ""]
        log_entries = [
            LogEntry(
                "2026-05-08 09:00", "question-closed", "r", "tried to close phantom", None,
                closes_questions=["Question that was never recorded?"],
            ),
        ]
        result = update_open_questions(existing, log_entries)
        # Real question still there
        assert any("Real question?" in line for line in result)

    def test_multiline_question_survives_file_roundtrip(self) -> None:
        """A multi-line question body must not truncate when pulse.md is written
        and re-read (which splits on newlines). It is stored as one line."""
        rendered = update_open_questions(
            ["## Open questions", "", "_None yet._", ""],
            [LogEntry("2026-05-08 09:00", "question", "r",
                      "Does drift exceed spec at 85C?\nAnd why does it?", None)],
        )
        # Simulate write-to-disk then read-back: join and re-split on newlines.
        reparsed = "\n".join(rendered).split("\n")
        result = update_open_questions(reparsed, [])
        bullets = [line for line in result if line.startswith("- ")]
        assert bullets == ["- Does drift exceed spec at 85C? And why does it?"]

    def test_multiline_question_closable_by_full_text(self) -> None:
        """After the round-trip, the stored question closes on its full wording."""
        rendered = update_open_questions(
            ["## Open questions", "", "_None yet._", ""],
            [LogEntry("2026-05-08 09:00", "question", "r",
                      "Does drift exceed spec?\nAnd why?", None)],
        )
        reparsed = "\n".join(rendered).split("\n")
        result = update_open_questions(
            reparsed,
            [LogEntry("2026-05-08 10:00", "question-closed", "r", "resolved", None,
                      closes_questions=["Does drift exceed spec? And why?"])],
        )
        assert not any("drift exceed spec" in line for line in result)


class TestParsePulseLogClosesDirective:
    """Tests for parsing the → closes: directive in question-closed entries."""

    def test_single_closes_directive(self) -> None:
        log = textwrap.dedent("""
            ## [2026-05-08 14:00] question-closed researcher
            Rule 152 confirmed not applicable based on 2024 amendment.
            → closes: Does Rule 152 apply here?
        """).strip()
        entries = parse_pulse_log(log)
        assert len(entries) == 1
        assert entries[0].event_type == "question-closed"
        assert entries[0].closes_questions == ["Does Rule 152 apply here?"]
        # The closes directive should NOT appear in the description
        assert "→ closes:" not in entries[0].description

    def test_multiple_closes_directives(self) -> None:
        log = textwrap.dedent("""
            ## [2026-05-08 14:00] question-closed researcher
            One decision retired two related questions.
            → closes: First question?
            → closes: Second question?
        """).strip()
        entries = parse_pulse_log(log)
        assert entries[0].closes_questions == ["First question?", "Second question?"]


# --- compact_area ---

class TestCompactArea:
    def _setup_area(self, tmp_path: Path) -> Path:
        """Create a minimal area with pulse.md, _journal/pulse.log, and empty kb/."""
        area_dir = tmp_path / "areas" / "research"
        (area_dir / "kb" / "findings").mkdir(parents=True)
        (area_dir / "kb" / "decisions").mkdir(parents=True)
        (area_dir / "kb" / "concepts").mkdir(parents=True)
        (area_dir / "kb" / "sources").mkdir(parents=True)
        (area_dir / "_journal").mkdir(parents=True)
        # Empty pulse.md template
        (area_dir / "pulse.md").write_text(textwrap.dedent("""
            # research — pulse

            _Initialized: 2026-05-08_

            ## Current focus

            _(set when work begins)_

            ## Recent decisions (last 7 active days)

            _None yet._

            ## Active concepts under test

            _None yet._

            ## Open questions

            _None yet._

            ## Recent findings (last 5)

            _None yet._
        """).strip() + "\n")
        (area_dir / "_journal" / "pulse.log").write_text("")
        return area_dir

    def test_empty_log_idempotent(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        result = compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        assert result.entries_compacted == 0
        assert not result.over_cap
        # pulse.md should still exist
        assert (area_dir / "pulse.md").is_file()

    def test_regenerates_recent_findings_from_kb(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        # Add two findings to the kb
        write_kb_page(tmp_path, "areas/research", "finding", "a")
        write_kb_page(tmp_path, "areas/research", "finding", "b")
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        pulse_content = (area_dir / "pulse.md").read_text()
        assert "f-2026-05-a" in pulse_content
        assert "f-2026-05-b" in pulse_content

    def test_regenerates_concepts_under_test(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "concept", "ut1",
            frontmatter_overrides={"status": "under_test", "evidence": ["[[s-foo]]"]},
        )
        write_kb_page(
            tmp_path, "areas/research", "concept", "dev1",
            frontmatter_overrides={"status": "developing"},
        )
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        pulse_content = (area_dir / "pulse.md").read_text()
        # Only the under_test one appears in that section
        assert "c-2026-05-ut1" in pulse_content
        # The developing concept doesn't show up as "under test"
        section_after_under_test = pulse_content.split("## Active concepts under test")[1]
        section_under_test_only = section_after_under_test.split("##")[0]
        assert "c-2026-05-dev1" not in section_under_test_only

    def test_log_focus_shift_updates_current_focus(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        (area_dir / "_journal" / "pulse.log").write_text(textwrap.dedent("""
            ## [2026-05-08 13:45] focus-shift optics-researcher
            Now investigating 1/f noise.
        """).strip() + "\n")
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        pulse_content = (area_dir / "pulse.md").read_text()
        assert "1/f noise" in pulse_content

    def test_log_question_added_to_open_questions(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        (area_dir / "_journal" / "pulse.log").write_text(textwrap.dedent("""
            ## [2026-05-08 11:00] question optics-researcher
            Does bias direction affect noise floor?
        """).strip() + "\n")
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        pulse_content = (area_dir / "pulse.md").read_text()
        assert "Does bias direction affect noise floor?" in pulse_content

    def test_log_is_truncated_after_compaction(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        (area_dir / "_journal" / "pulse.log").write_text("## [2026-05-08 09:00] question r\nq?\n")
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        log_after = (area_dir / "_journal" / "pulse.log").read_text()
        assert log_after == ""

    def test_missing_filed_path_warned(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        (area_dir / "_journal" / "pulse.log").write_text(textwrap.dedent("""
            ## [2026-05-08 09:00] decision r
            A decision.
            → to be filed: decisions/d-2026-05-not-actually-filed
        """).strip() + "\n")
        result = compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        assert "decisions/d-2026-05-not-actually-filed" in result.missing_filed_paths

    def test_repo_root_filed_path_resolves(self, tmp_path: Path) -> None:
        """A repo-root `→ to be filed:` path (areas/<area>/kb/...) still resolves
        against the area kb — no spurious 'not found on disk' warning."""
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "filed")  # f-2026-05-filed
        (area_dir / "_journal" / "pulse.log").write_text(textwrap.dedent("""
            ## [2026-05-08 09:00] finding r
            A finding, filed with a repo-root path.
            → to be filed: areas/research/kb/findings/f-2026-05-filed
        """).strip() + "\n")
        result = compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        assert result.missing_filed_paths == []

    def test_commons_repo_root_filed_path_resolves(self, tmp_path: Path) -> None:
        """The commons/kb/ prefix is stripped too."""
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "cfiled")  # f-2026-05-cfiled
        (area_dir / "_journal" / "pulse.log").write_text(textwrap.dedent("""
            ## [2026-05-08 09:00] finding r
            A finding.
            → to be filed: commons/kb/findings/f-2026-05-cfiled
        """).strip() + "\n")
        result = compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        assert result.missing_filed_paths == []

    def test_over_cap_detected(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        # Add 20 findings to ensure pulse will be bigger than tight cap
        for i in range(20):
            write_kb_page(tmp_path, "areas/research", "finding", f"f{i}")
        result = compact_area(area_dir, tmp_path, {"lint": {"pulse_line_cap": 10, "recent_decisions_window_active_days": 7}})
        assert result.over_cap

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running compact twice produces identical pulse.md the second time."""
        make_minimal_repo(tmp_path)
        area_dir = self._setup_area(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "a")
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        first = (area_dir / "pulse.md").read_text()
        compact_area(area_dir, tmp_path, DEFAULT_CONFIG)
        second = (area_dir / "pulse.md").read_text()
        assert first == second


# --- first_sentence ---

class TestFirstSentence:
    def test_plain_two_sentences(self) -> None:
        assert first_sentence("Chose Postgres. Considered MySQL.") == "Chose Postgres"

    def test_strips_trailing_terminator(self) -> None:
        assert first_sentence("Adopted the new schema.") == "Adopted the new schema"

    def test_no_terminator_returns_whole(self) -> None:
        assert first_sentence("Bumped the pinned version") == "Bumped the pinned version"

    def test_decimal_version_not_split(self) -> None:
        assert first_sentence("Shipped v3.5 of the API.") == "Shipped v3.5 of the API"

    def test_decimal_version_no_trailing_period(self) -> None:
        assert first_sentence("Bumped to 3.5") == "Bumped to 3.5"

    def test_exclamation_and_question(self) -> None:
        assert first_sentence("It works! Ship it.") == "It works"
        assert first_sentence("Ready? Not yet.") == "Ready"

    def test_abbreviation_eg_not_split(self) -> None:
        assert first_sentence("Use a cache, e.g. Redis, for hot keys.") == (
            "Use a cache, e.g. Redis, for hot keys"
        )

    def test_abbreviation_ie_not_split(self) -> None:
        assert first_sentence("Prefer the lint tool, i.e. run check first.") == (
            "Prefer the lint tool, i.e. run check first"
        )

    def test_abbreviation_titles_not_split(self) -> None:
        assert first_sentence("Met Dr. Lee about the rig.") == "Met Dr. Lee about the rig"
        assert first_sentence("Mr. and Mrs. Chen signed off.") == "Mr. and Mrs. Chen signed off"

    def test_abbreviation_case_insensitive(self) -> None:
        assert first_sentence("Compared options, E.G. Postgres vs MySQL.") == (
            "Compared options, E.G. Postgres vs MySQL"
        )

    def test_abbreviation_at_end_returns_whole(self) -> None:
        assert first_sentence("Followed up with Dr.") == "Followed up with Dr."

    def test_additional_abbreviations(self) -> None:
        assert first_sentence("Compared A vs. B on the bench.") == "Compared A vs. B on the bench"
        assert first_sentence("See Smith et al. for the derivation.") == (
            "See Smith et al. for the derivation"
        )
        assert first_sentence("Refer to fig. 4 for the layout.") == "Refer to fig. 4 for the layout"
        assert first_sentence("Plug into eq. 2 and solve.") == "Plug into eq. 2 and solve"
        assert first_sentence("Added logs, metrics, etc. all wired up.") == (
            "Added logs, metrics, etc. all wired up"
        )

    def test_empty_and_whitespace(self) -> None:
        assert first_sentence("") == ""
        assert first_sentence("   ") == ""

    def test_real_second_sentence_still_splits_after_abbreviation(self) -> None:
        assert first_sentence("Use e.g. Redis. Details in the finding.") == (
            "Use e.g. Redis"
        )

    def test_abbreviation_not_matched_as_word_suffix(self) -> None:
        # " no." must not fire inside "casino."; " ca." not inside "Rica."
        assert first_sentence("We visited the casino. Then home.") == "We visited the casino"
        assert first_sentence("Flew to Costa Rica. Then back.") == "Flew to Costa Rica"

    def test_single_letter_initial_not_split(self) -> None:
        assert first_sentence("Fitted by W. Gurnee in 2024.") == "Fitted by W. Gurnee in 2024"

    def test_initial_at_start_not_truncated(self) -> None:
        assert first_sentence("W. Gurnee ran the fit. Results held.") == "W. Gurnee ran the fit"

    def test_abbreviation_at_start_not_truncated(self) -> None:
        assert first_sentence("Vs. the baseline, latency dropped. Details below.") == (
            "Vs. the baseline, latency dropped"
        )

    def test_newly_added_abbreviations(self) -> None:
        assert first_sentence("Compare cf. the prior finding for context.") == (
            "Compare cf. the prior finding for context"
        )
        assert first_sentence("Runtime is approx. 2x on the new rig.") == (
            "Runtime is approx. 2x on the new rig"
        )
        assert first_sentence("Cited in sec. 3 of the paper.") == "Cited in sec. 3 of the paper"
        assert first_sentence("Tracked as no. 5 in the queue.") == "Tracked as no. 5 in the queue"
        assert first_sentence("Filed with the U.S. regulator last week.") == (
            "Filed with the U.S. regulator last week"
        )
        assert first_sentence("Reviewed by her Ph.D. advisor first.") == (
            "Reviewed by her Ph.D. advisor first"
        )
