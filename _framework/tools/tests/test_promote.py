"""
Tests for _framework/tools/promote.py
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pytest

from promote import PromoteError, promote
from common import dump_frontmatter_body, extract_wikilinks, parse_frontmatter

from lint_helpers import make_minimal_repo


def _write_proposal(repo_root: Path, slug: str, page_type: str, page_id: str,
                    *, source_area: str = "research") -> Path:
    """Create a commons/_proposed/<slug>/ with page.md and proposal.md."""
    proposed = repo_root / "commons" / "_proposed" / slug
    proposed.mkdir(parents=True)

    page = proposed / "page.md"
    page.write_text(textwrap.dedent(f"""
        ---
        id: {page_id}
        title: Test {page_type}
        type: {page_type}
        status: active
        area: {source_area}
        created: 2026-05-08
        updated: 2026-05-08
        summary: A test {page_type} for promotion.
        relevant_to:
          - test
        {"provenance:" if page_type == "finding" else "alternatives_considered: []" if page_type == "decision" else ""}
        {"  kind: experiment" if page_type == "finding" else ""}
        ---

        Body of the {page_type}.
    """).strip() + "\n")

    proposal = proposed / "proposal.md"
    proposal.write_text(textwrap.dedent(f"""
        ---
        proposing_area: {source_area}
        proposed_on: 2026-05-08
        ---

        # Proposal: promote {page_id}

        Rationale here.
    """).strip() + "\n")

    return proposed


class TestPromote:
    def test_moves_page_to_kb(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _write_proposal(tmp_path, "2026-05-shot-noise", "finding", "f-2026-05-shot-noise")
        result = promote("2026-05-shot-noise", tmp_path)

        # Target file uses the new commons-id form (date dropped)
        target = tmp_path / "commons" / "kb" / "findings" / "f-commons-shot-noise.md"
        assert target.is_file()
        assert result.moved_to == "commons/kb/findings/f-commons-shot-noise.md"
        assert result.source_page_id == "f-2026-05-shot-noise"
        assert result.new_commons_id == "f-commons-shot-noise"
        # Original page.md should be gone
        assert not (tmp_path / "commons" / "_proposed" / "2026-05-shot-noise" / "page.md").exists()
        # Other files in the proposal dir remain
        assert (tmp_path / "commons" / "_proposed" / "2026-05-shot-noise" / "proposal.md").exists()

    def test_updates_frontmatter(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _write_proposal(tmp_path, "test-slug", "finding", "f-2026-05-test")
        promote("test-slug", tmp_path)

        target = tmp_path / "commons" / "kb" / "findings" / "f-commons-test.md"
        content = target.read_text()
        # Aligned with commons-extension's frontmatter shape
        assert "id: f-commons-test" in content
        assert "area: commons" in content
        assert "human_reviewed: false" in content
        assert "promoted_from_page: f-2026-05-test" in content
        assert "promoted_from_area: research" in content
        assert "promotion_path: proposal-and-promote" in content
        assert f"promoted_on: {date.today().isoformat()}" in content

    def test_preserves_body(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _write_proposal(tmp_path, "test-slug", "finding", "f-2026-05-test")
        promote("test-slug", tmp_path)

        target = tmp_path / "commons" / "kb" / "findings" / "f-commons-test.md"
        content = target.read_text()
        assert "Body of the finding." in content

    def test_writes_changelog_entry(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Pre-create CHANGELOG with the standard intro
        changelog = tmp_path / "commons" / "CHANGELOG.md"
        changelog.write_text("# Commons Changelog\n\n_Append-only record._\n\n_No promotions yet._\n")

        _write_proposal(tmp_path, "test-slug", "finding", "f-2026-05-test")
        promote("test-slug", tmp_path)

        content = changelog.read_text()
        assert "promoted finding" in content
        # CHANGELOG cites the new commons id, not the source
        assert "[[f-commons-test]]" in content
        assert "From: research" in content
        # Placeholder should be gone (or at least the new entry should be near the top)
        new_pos = content.find("promoted finding")
        placeholder_pos = content.find("_No promotions yet._")
        if placeholder_pos != -1:
            assert new_pos < placeholder_pos

    def test_decision_goes_to_decisions_dir(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _write_proposal(tmp_path, "decision-slug", "decision", "d-2026-05-test")
        result = promote("decision-slug", tmp_path)
        assert result.moved_to == "commons/kb/decisions/d-commons-test.md"
        assert (tmp_path / "commons" / "kb" / "decisions" / "d-commons-test.md").is_file()

    def test_concept_goes_to_concepts_dir(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Concept proposals: write manually since helper assumes finding/decision
        proposed = tmp_path / "commons" / "_proposed" / "concept-slug"
        proposed.mkdir(parents=True)
        (proposed / "page.md").write_text(textwrap.dedent("""
            ---
            id: c-2026-05-test
            title: Test concept
            type: concept
            status: supported
            area: research
            created: 2026-05-08
            updated: 2026-05-08
            summary: A test concept.
            relevant_to:
              - test
            evidence:
              - "[[s-foo]]"
            ---

            Concept body.
        """).strip() + "\n")
        (proposed / "proposal.md").write_text(
            "---\nproposing_area: research\nproposed_on: 2026-05-08\n---\n\nProposal.\n"
        )
        result = promote("concept-slug", tmp_path)
        assert result.moved_to == "commons/kb/concepts/c-commons-test.md"

    def test_missing_proposal_raises(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        with pytest.raises(PromoteError):
            promote("nonexistent", tmp_path)

    def test_target_exists_raises(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _write_proposal(tmp_path, "test-slug", "finding", "f-2026-05-test")
        # Pre-create the target — must use the new commons id form
        target_dir = tmp_path / "commons" / "kb" / "findings"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "f-commons-test.md").write_text("existing")
        with pytest.raises(PromoteError) as exc_info:
            promote("test-slug", tmp_path)
        assert "already exists" in str(exc_info.value)

    def test_preserves_frontmatter_wikilinks(self, tmp_path: Path) -> None:
        """Regression (Issue 1): promote must not mangle [[wikilinks]] in
        frontmatter into nested YAML sequences, and must keep `|` block scalars."""
        make_minimal_repo(tmp_path)
        proposed = tmp_path / "commons" / "_proposed" / "links-slug"
        proposed.mkdir(parents=True)
        (proposed / "page.md").write_text(textwrap.dedent("""
            ---
            id: f-2026-05-links
            title: Test finding
            type: finding
            status: active
            area: research
            created: 2026-05-08
            updated: 2026-05-08
            summary: A finding with wikilink frontmatter.
            relevant_to:
              - test
            when_to_load: |
              Load when checking the coverage claim.
              Skip for orientation.
            provenance:
              kind: external
              ref: [[sources/s-2026-05-src]]
            evidence:
              - [[sources/s-2026-05-src]]
              - [[findings/f-2026-05-other]]
            alternatives_considered:
              - [[concepts/c-2026-05-alt]]
            ---

            Body.
        """).strip() + "\n")
        (proposed / "proposal.md").write_text(
            "---\nproposing_area: research\nproposed_on: 2026-05-08\n---\n\nProposal.\n"
        )
        promote("links-slug", tmp_path)

        content = (tmp_path / "commons" / "kb" / "findings" / "f-commons-links.md").read_text()
        # No nested-sequence corruption ("- - - sources/...")
        assert "- - " not in content
        # Wikilinks survive as resolvable text
        fm, _ = parse_frontmatter(content)
        assert extract_wikilinks(fm["provenance"]["ref"]) == ["sources/s-2026-05-src"]
        assert extract_wikilinks(fm["evidence"][0]) == ["sources/s-2026-05-src"]
        assert extract_wikilinks(fm["evidence"][1]) == ["findings/f-2026-05-other"]
        assert extract_wikilinks(fm["alternatives_considered"][0]) == ["concepts/c-2026-05-alt"]
        # Block scalar preserved (value intact; not re-emitted as a mangled quoted scalar)
        assert fm["when_to_load"].splitlines()[:2] == [
            "Load when checking the coverage claim.",
            "Skip for orientation.",
        ]


class TestFrontmatterWikilinkRoundtrip:
    """Direct coverage of the common.py quote-on-read / dump helpers (Issue 1)."""

    def test_unquoted_wikilink_scalar_survives(self) -> None:
        fm, _ = parse_frontmatter("---\nref: [[sources/s-x]]\n---\nbody\n")
        assert fm["ref"] == "[[sources/s-x]]"  # string, not [['sources/s-x']]
        out = dump_frontmatter_body(fm)
        assert extract_wikilinks(out) == ["sources/s-x"]
        assert "- - " not in out

    def test_unquoted_wikilink_list_survives(self) -> None:
        fm, _ = parse_frontmatter("---\nevidence:\n  - [[a/b]]\n  - [[c/d]]\n---\nbody\n")
        assert fm["evidence"] == ["[[a/b]]", "[[c/d]]"]
        out = dump_frontmatter_body(fm)
        assert extract_wikilinks(out) == ["a/b", "c/d"]

    def test_already_quoted_is_idempotent(self) -> None:
        fm, _ = parse_frontmatter('---\nref: "[[sources/s-x]]"\n---\nbody\n')
        assert fm["ref"] == "[[sources/s-x]]"
