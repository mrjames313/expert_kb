"""Tests for commons_extension.py."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import commons_extension as ce


# --- Test helpers ---

def _write_page(path: Path, fm_yaml: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\n{fm_yaml}---\n\n{body}\n"
    path.write_text(content, encoding="utf-8")


def make_minimal_repo(tmp: Path) -> None:
    (tmp / "areas").mkdir()
    (tmp / "commons" / "kb" / "findings").mkdir(parents=True)
    (tmp / "commons" / "kb" / "decisions").mkdir(parents=True)
    (tmp / "commons" / "kb" / "concepts").mkdir(parents=True)


def add_area_with_finding(tmp: Path, area: str, page_id: str, **fm_overrides) -> Path:
    """Add an area with a single finding. Returns the page path."""
    area_dir = tmp / "areas" / area / "kb" / "findings"
    fm = {
        "id": page_id,
        "title": f"Title for {page_id}",
        "type": "finding",
        "status": "active",
        "area": area,
        "created": "2026-05-15",
        "updated": "2026-05-15",
        "summary": "A summary.",
        "provenance": {"kind": "external", "ref": "x", "raw_path": "~"},
        "evidence": ["x"],
        "confidence": "high",
    }
    fm.update(fm_overrides)
    fm_yaml = "".join(
        f"{k}: {v if not isinstance(v, dict) else str(v)}\n"
        for k, v in fm.items()
    )
    page_path = area_dir / f"{page_id}.md"
    _write_page(page_path, fm_yaml, "Original body content.")
    return page_path


# --- Tests for _new_commons_id ---

class TestNewCommonsId:
    def test_finding_with_full_date(self) -> None:
        assert ce._new_commons_id("f-2026-05-26-accredited-investor") == \
            "f-commons-accredited-investor"

    def test_decision_with_full_date(self) -> None:
        assert ce._new_commons_id("d-2026-05-27-dd-playbook-v1") == \
            "d-commons-dd-playbook-v1"

    def test_concept_with_year_month_only(self) -> None:
        assert ce._new_commons_id("c-2026-05-shot-noise") == \
            "c-commons-shot-noise"

    def test_multi_word_slug(self) -> None:
        assert ce._new_commons_id("f-2026-05-26-reg-d-506b-vs-506c") == \
            "f-commons-reg-d-506b-vs-506c"

    def test_non_conforming_id(self) -> None:
        # Falls back to safe prefixing
        result = ce._new_commons_id("weird-id")
        assert result.startswith("weird-")
        assert "commons" in result

    def test_idempotent_on_commons_id(self) -> None:
        # Regression (bug report #2): re-running the generator on an id that is
        # already in commons form must return it unchanged, not fork a second
        # `…-commons-commons-…` page.
        for cid in (
            "f-commons-accredited-investor",
            "d-commons-dd-playbook-v1",
            "c-commons-shot-noise",
            "f-commons",
        ):
            assert ce._new_commons_id(cid) == cid

    def test_slug_word_containing_commons_is_not_treated_as_commons_id(self) -> None:
        # "commons" appearing later in the slug (not position 1) is a normal id.
        assert ce._new_commons_id("f-2026-05-commons-governance") == \
            "f-commons-commons-governance"

    def test_generated_id_passes_lint_validation(self) -> None:
        """The id form commons_extension generates must pass is_valid_id."""
        from common import is_valid_id
        for source_id, page_type in [
            ("f-2026-05-26-accredited-investor", "finding"),
            ("d-2026-05-27-dd-playbook-v1", "decision"),
            ("c-2026-05-shot-noise", "concept"),
        ]:
            new_id = ce._new_commons_id(source_id)
            assert is_valid_id(new_id, page_type), \
                f"generated id {new_id!r} failed lint validation for type {page_type!r}"


# --- Tests for list_candidates ---

class TestListCandidates:
    def test_empty_project(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        candidates, ctx = ce.list_candidates(tmp_path, "newarea")
        assert candidates == []
        assert ctx.area_count == 0
        assert ctx.candidate_count == 0
        assert ctx.existing_area_kb_size == 0

    def test_single_area_finding_is_candidate(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-test-finding")
        candidates, ctx = ce.list_candidates(tmp_path, "newarea")
        assert len(candidates) == 1
        assert candidates[0].page_id == "f-2026-05-26-test-finding"
        assert candidates[0].source_area == "research"
        assert ctx.area_count == 1
        assert ctx.existing_area_kb_size == 1
        assert ctx.candidate_count == 1

    def test_superseded_excluded(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-good", status="active")
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-old",
                              status="superseded", superseded_by="f-2026-05-26-good")
        candidates, ctx = ce.list_candidates(tmp_path, "newarea")
        ids = [c.page_id for c in candidates]
        assert "f-2026-05-26-good" in ids
        assert "f-2026-05-26-old" not in ids

    def test_falsified_dropped_archived_excluded(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        for status in ("falsified", "dropped", "archived"):
            add_area_with_finding(tmp_path, "research", f"f-2026-05-26-{status}", status=status)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-active", status="active")
        candidates, _ = ce.list_candidates(tmp_path, "newarea")
        ids = [c.page_id for c in candidates]
        assert ids == ["f-2026-05-26-active"]

    def test_commons_pages_not_candidates(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Page already in commons
        commons_fm = (
            "id: f-commons-pre-existing\ntitle: Pre-existing\ntype: finding\n"
            "status: active\narea: commons\ncreated: 2026-04-01\nupdated: 2026-04-01\n"
            "summary: Already there.\n"
            "provenance: {kind: external, ref: x, raw_path: '~'}\n"
            "evidence: [x]\nconfidence: high\n"
        )
        _write_page(tmp_path / "commons" / "kb" / "findings" / "f-commons-pre-existing.md",
                    commons_fm, "Already in commons.")
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-area-finding")
        candidates, ctx = ce.list_candidates(tmp_path, "newarea")
        ids = [c.page_id for c in candidates]
        assert "f-commons-pre-existing" not in ids
        assert "f-2026-05-26-area-finding" in ids
        assert ctx.existing_commons_size == 1
        assert ctx.existing_area_kb_size == 1

    def test_when_to_load_preserved(self, tmp_path: Path) -> None:
        """The when_to_load field should pass through to the Candidate."""
        make_minimal_repo(tmp_path)
        area_dir = tmp_path / "areas" / "research" / "kb" / "findings"
        page_path = area_dir / "f-2026-05-26-with-wtl.md"
        page_path.parent.mkdir(parents=True)
        page_path.write_text(textwrap.dedent("""\
            ---
            id: f-2026-05-26-with-wtl
            title: Has when_to_load
            type: finding
            status: active
            area: research
            created: 2026-05-26
            updated: 2026-05-26
            summary: x
            when_to_load: |
              Read when needing this specific kind of content.
            provenance:
              kind: external
              ref: x
              raw_path: ~
            evidence: [x]
            confidence: high
            ---

            Body.
            """), encoding="utf-8")
        candidates, _ = ce.list_candidates(tmp_path, "newarea")
        assert len(candidates) == 1
        assert candidates[0].when_to_load is not None
        assert "Read when needing" in candidates[0].when_to_load

    def test_sources_excluded_by_default(self, tmp_path: Path) -> None:
        """Source pages should not surface as candidates (defaults exclude them)."""
        make_minimal_repo(tmp_path)
        area_dir = tmp_path / "areas" / "research" / "kb" / "sources"
        page_path = area_dir / "s-2026-05-26-some-source.md"
        page_path.parent.mkdir(parents=True)
        page_path.write_text(textwrap.dedent("""\
            ---
            id: s-2026-05-26-some-source
            title: A source
            type: source
            status: active
            area: research
            created: 2026-05-26
            updated: 2026-05-26
            summary: x
            provenance:
              kind: external
              retrieved: 2026-05-26
              raw_path: research/raw/foo.html
            ---

            Source body.
            """), encoding="utf-8")
        candidates, _ = ce.list_candidates(tmp_path, "newarea")
        assert candidates == []


# --- Tests for apply_extension ---

class TestApplyExtension:
    def test_basic_copy_as_is(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-test-finding")
        result = ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea")
        # Commons file was created
        assert Path(result.new_commons_path).name == "f-commons-test-finding.md"
        commons_path = tmp_path / result.new_commons_path
        assert commons_path.exists()
        # Source page is untouched
        source_path = tmp_path / "areas" / "research" / "kb" / "findings" / "f-2026-05-26-test-finding.md"
        assert source_path.exists()
        # New frontmatter has commons indicators
        new_text = commons_path.read_text(encoding="utf-8")
        assert "area: commons" in new_text
        assert "promoted_from_page: f-2026-05-26-test-finding" in new_text
        assert "promoted_from_area: research" in new_text
        assert "promotion_path: commons-extension" in new_text
        assert "promoted_during_add_area: newarea" in new_text
        # Body was copied verbatim (refined=False)
        assert "Original body content." in new_text
        assert result.refined is False

    def test_drops_relevant_to_on_commons(self, tmp_path: Path) -> None:
        """relevant_to is omitted on commons pages (Issue 5e)."""
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-rt", relevant_to=["thermal"])
        result = ce.apply_extension(tmp_path, "f-2026-05-26-rt", "newarea")
        new_text = (tmp_path / result.new_commons_path).read_text(encoding="utf-8")
        assert "relevant_to" not in new_text

    def test_sets_commons_twin_and_aligned_on(self, tmp_path: Path) -> None:
        """Commons-extension sets aligned_on and the commons_twin back-pointer
        (Phase 3b — parity with /promote)."""
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-tw")
        result = ce.apply_extension(tmp_path, "f-2026-05-26-tw", "newarea")
        assert result.twin_backpointer_set is True
        src = (tmp_path / "areas/research/kb/findings/f-2026-05-26-tw.md").read_text()
        assert 'commons_twin: "[[f-commons-tw]]"' in src
        commons = (tmp_path / result.new_commons_path).read_text()
        assert "aligned_on:" in commons

    def test_with_refined_body(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-test-finding")
        refined = "Refined body for general framing.\n"
        result = ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea",
                                    refined_body=refined)
        commons_path = tmp_path / result.new_commons_path
        new_text = commons_path.read_text(encoding="utf-8")
        assert "Refined body for general framing." in new_text
        assert "Original body content." not in new_text
        assert result.refined is True

    def test_changelog_appended(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-test-finding")
        ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea")
        changelog = tmp_path / "commons" / "CHANGELOG.md"
        assert changelog.exists()
        text = changelog.read_text(encoding="utf-8")
        assert "commons-extension" in text
        assert "f-commons-test-finding" in text
        assert "f-2026-05-26-test-finding" in text
        assert "/add-area newarea" in text

    def test_source_id_not_found_raises(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        with pytest.raises(RuntimeError, match="source page not found"):
            ce.apply_extension(tmp_path, "f-2026-05-26-nonexistent", "newarea")

    def test_existing_commons_target_raises(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        add_area_with_finding(tmp_path, "research", "f-2026-05-26-test-finding")
        # First application succeeds
        ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea")
        # Second application fails (target exists)
        with pytest.raises(RuntimeError, match="already exists"):
            ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea")

    def test_source_page_only_gains_commons_twin(self, tmp_path: Path) -> None:
        """Commons extension leaves the source area page's content intact,
        adding only the commons_twin back-pointer (the sanctioned exception)."""
        make_minimal_repo(tmp_path)
        source_path = add_area_with_finding(
            tmp_path, "research", "f-2026-05-26-test-finding"
        )
        original = source_path.read_text(encoding="utf-8")
        ce.apply_extension(tmp_path, "f-2026-05-26-test-finding", "newarea")
        after = source_path.read_text(encoding="utf-8")
        twin_line = 'commons_twin: "[[f-commons-test-finding]]"\n'
        assert twin_line in after
        assert after.replace(twin_line, "") == original
