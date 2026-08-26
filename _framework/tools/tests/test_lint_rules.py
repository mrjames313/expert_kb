"""
Tests for lint rules in commit 2a.

Each rule gets a TestRuleNN class with at least one pass case and a fail case
per kind of violation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lint_rules import (
    rule_01_frontmatter,
    rule_02_forward_links,
    rule_03_backlinks,
    rule_05_supersession,
    rule_06_completeness,
    rule_07_pulse_size,
    rule_12_manifest,
    rule_15_index,
    rule_18_id_uniqueness,
    rule_20_commons_drift,
    rule_21_commons_twin_links,
)

from lint_helpers import make_minimal_repo, write_kb_page


DEFAULT_CONFIG = {"lint": {"pulse_line_cap": 80}}


# --- Rule 1: Frontmatter validity ---

class TestRule01Frontmatter:
    def test_clean_repo(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "ok")
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_missing_frontmatter_block(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        kb = tmp_path / "areas" / "research" / "kb" / "findings"
        kb.mkdir(parents=True)
        (kb / "f-2026-05-bad.md").write_text("# No frontmatter here\n\nJust body.\n")
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("missing frontmatter" in f.message for f in findings)

    def test_invalid_type(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "finding", "ok",
            frontmatter_overrides={"type": "bogus"},
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("invalid type" in f.message for f in findings)

    def test_invalid_status_for_type(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "decision", "ok",
            frontmatter_overrides={"status": "developing"},  # not valid for decision
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("invalid status" in f.message for f in findings)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        kb = tmp_path / "areas" / "research" / "kb" / "findings"
        kb.mkdir(parents=True)
        (kb / "f-2026-05-incomplete.md").write_text(
            "---\nid: f-2026-05-incomplete\ntitle: x\ntype: finding\n---\n\nbody\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        # Several required fields missing
        missing_msgs = [f.message for f in findings if "missing required" in f.message]
        assert len(missing_msgs) >= 3

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        kb = tmp_path / "areas" / "research" / "kb" / "findings"
        kb.mkdir(parents=True)
        (kb / "f-2026-05-broken.md").write_text(
            "---\nid: f-2026-05-broken\nthis is: not\n  : valid yaml\n---\n\nbody\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("malformed frontmatter" in f.message for f in findings)

    def test_bad_id_convention(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "finding", "ok",
            frontmatter_overrides={"id": "no-prefix-here"},
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("does not match convention" in f.message for f in findings)

    def test_duplicate_frontmatter_block_in_kb_page(self, tmp_path: Path) -> None:
        """Two `---`-delimited blocks at the top of a kb page is flagged."""
        make_minimal_repo(tmp_path)
        kb = tmp_path / "areas" / "research" / "kb" / "findings"
        kb.mkdir(parents=True)
        (kb / "f-2026-05-dup.md").write_text(
            "---\n"
            "id: f-2026-05-dup\n"
            "title: x\ntype: finding\nstatus: active\narea: research\n"
            "created: 2026-05-08\nupdated: 2026-05-08\n"
            "---\n"
            "id: f-2026-05-dup\n"
            "title: x\ntype: finding\nstatus: active\narea: research\n"
            "created: 2026-05-08\nupdated: 2026-05-08\n"
            "summary: x\n"
            "---\n\n"
            "body\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("duplicate frontmatter" in f.message for f in findings)

    def test_spec_brief_with_duplicate_frontmatter_flagged(self, tmp_path: Path) -> None:
        """Spec files (brief/plan/tasks/outcome) are scanned with relaxed checks
        — only structural issues like duplicate frontmatter get flagged."""
        make_minimal_repo(tmp_path)
        spec_dir = tmp_path / "areas" / "research" / "specs" / "test-spec"
        spec_dir.mkdir(parents=True)
        # Reproduce the user's actual pattern: two `---`-delimited blocks at the top
        (spec_dir / "brief.md").write_text(
            "---\n"
            "id: d-2026-05-test\n"
            "title: test\ntype: decision\nstatus: active\narea: research\n"
            "created: 2026-05-26\nupdated: 2026-05-26\n"
            "---\n"
            "id: d-2026-05-test\n"
            "title: test\ntype: decision\nstatus: active\narea: research\n"
            "created: 2026-05-26\nupdated: 2026-05-26\n"
            "summary: test summary\n"
            "---\n\n"
            "# test\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        # The brief is flagged
        assert any(
            "brief.md" in f.file_path and "duplicate frontmatter" in f.message
            for f in findings
        )

    def test_spec_brief_pure_prose_no_findings(self, tmp_path: Path) -> None:
        """Briefs with no frontmatter at all are fine — they're prose by design."""
        make_minimal_repo(tmp_path)
        spec_dir = tmp_path / "areas" / "research" / "specs" / "test-spec"
        spec_dir.mkdir(parents=True)
        (spec_dir / "brief.md").write_text("# Test\n\nProse only, no frontmatter.\n")
        (spec_dir / "plan.md").write_text("# Plan\n\nMore prose.\n")
        (spec_dir / "tasks.md").write_text("# Tasks\n\n- T1\n")
        (spec_dir / "outcome.md").write_text("# Outcome\n\nFinal prose.\n")
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        # No findings about any spec file
        spec_findings = [f for f in findings if "/specs/" in f.file_path]
        assert spec_findings == []

    def test_spec_brief_with_valid_frontmatter_no_required_fields_check(self, tmp_path: Path) -> None:
        """If a spec file has frontmatter, only structural validity is checked
        — required-field validation is skipped (the spec layer doesn't impose
        a schema on briefs)."""
        make_minimal_repo(tmp_path)
        spec_dir = tmp_path / "areas" / "research" / "specs" / "test-spec"
        spec_dir.mkdir(parents=True)
        # Frontmatter present but with no `id`, `type`, etc. — kb pages would
        # be flagged, but spec files are not.
        (spec_dir / "brief.md").write_text(
            "---\n"
            "spec: test-spec\n"
            "owner: alice\n"
            "---\n\n"
            "# Brief\n\nFreeform frontmatter, structurally valid.\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        spec_findings = [f for f in findings if "brief.md" in f.file_path]
        assert spec_findings == []

    def test_spec_file_malformed_yaml_flagged(self, tmp_path: Path) -> None:
        """Even though spec files have no required fields, broken YAML is still flagged."""
        make_minimal_repo(tmp_path)
        spec_dir = tmp_path / "areas" / "research" / "specs" / "test-spec"
        spec_dir.mkdir(parents=True)
        (spec_dir / "brief.md").write_text(
            "---\n"
            "this is: not\n"
            "  : valid yaml\n"
            "---\n\n"
            "body\n"
        )
        findings = rule_01_frontmatter.check(tmp_path, DEFAULT_CONFIG)
        assert any("brief.md" in f.file_path and "malformed" in f.message for f in findings)


# --- Rule 2: Forward-link integrity ---

class TestRule02ForwardLinks:
    def test_resolved_link(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "concept", "shot-noise")
        write_kb_page(
            tmp_path, "areas/research", "finding", "with-link",
            body="Builds on [[c-2026-05-shot-noise]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_broken_link(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "finding", "broken-link",
            body="Links to [[c-2026-05-does-not-exist]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert any("does not resolve" in f.message for f in findings)

    def test_raw_path_resolves(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Create the raw file
        raw_dir = tmp_path / "areas" / "research" / "raw" / "papers"
        raw_dir.mkdir(parents=True)
        (raw_dir / "paper.pdf").write_text("fake pdf bytes")
        # Create a source page pointing at it
        write_kb_page(
            tmp_path, "areas/research", "source", "paper",
            extra_frontmatter_yaml="provenance:\n  kind: external\n  retrieved: 2026-05-01\n  raw_path: areas/research/raw/papers/paper.pdf",
            frontmatter_overrides={"summary": "Test source"},
        )
        # Need to drop the default provenance our helper added — easier: just write a custom source.
        # Our helper already added one provenance; rewriting manually:
        page = tmp_path / "areas" / "research" / "kb" / "sources" / "s-2026-05-paper.md"
        page.write_text(
            "---\n"
            "id: s-2026-05-paper\n"
            "title: Test paper\n"
            "type: source\n"
            "status: active\n"
            "area: research\n"
            "created: 2026-05-08\n"
            "updated: 2026-05-08\n"
            "summary: Test source\n"
            "provenance:\n"
            "  kind: external\n"
            "  retrieved: 2026-05-01\n"
            "  raw_path: areas/research/raw/papers/paper.pdf\n"
            "---\n\n"
            "Body.\n"
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        # No findings about raw_path
        assert not any("raw_path" in f.message for f in findings)

    def test_raw_path_missing(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        page = tmp_path / "areas" / "research" / "kb" / "sources" / "s-2026-05-missing.md"
        page.parent.mkdir(parents=True)
        page.write_text(
            "---\n"
            "id: s-2026-05-missing\n"
            "title: x\ntype: source\nstatus: active\narea: research\n"
            "created: 2026-05-08\nupdated: 2026-05-08\nsummary: x\n"
            "provenance:\n  kind: external\n  raw_path: areas/research/raw/nope.pdf\n"
            "---\n\nx\n"
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert any("raw_path does not resolve" in f.message for f in findings)

    def test_cross_area_prefix_ok(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/engineering", "finding", "thermal")
        write_kb_page(
            tmp_path, "areas/research", "finding", "cites-eng",
            body="See [[engineering:findings/f-2026-05-thermal]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_cross_area_prefix_mismatch(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/engineering", "finding", "thermal")
        write_kb_page(
            tmp_path, "areas/research", "finding", "wrong-prefix",
            body="See [[research:f-2026-05-thermal]].",  # actually lives in engineering
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert any(
            "declares area 'research'" in f.message and "engineering" in f.message
            for f in findings
        )

    def test_nested_area_prefix_ok(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research/optics", "concept", "coating")
        write_kb_page(
            tmp_path, "areas/research", "finding", "cites-optics",
            body="Builds on [[research/optics:concepts/c-2026-05-coating]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_commons_prefix_ok(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "commons", "decision", "policy")
        write_kb_page(
            tmp_path, "areas/research", "finding", "cites-commons",
            body="Per [[commons:decisions/d-2026-05-policy]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_unprefixed_cross_area_still_resolves(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/engineering", "finding", "thermal")
        write_kb_page(
            tmp_path, "areas/research", "finding", "bare-xarea",
            body="See [[f-2026-05-thermal]].",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_frontmatter_wikilink_resolves(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "source", "src")
        write_kb_page(
            tmp_path, "areas/research", "concept", "cited",
            frontmatter_overrides={"status": "supported", "evidence": ["[[s-2026-05-src]]"]},
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_frontmatter_wikilink_broken(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "concept", "badcite",
            frontmatter_overrides={"status": "supported", "evidence": ["[[s-2026-05-nope]]"]},
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert any(
            "frontmatter wikilink" in f.message and "does not resolve" in f.message
            for f in findings
        )

    def test_frontmatter_wikilink_prefix_mismatch(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/engineering", "source", "src")
        write_kb_page(
            tmp_path, "areas/research", "concept", "wrongarea",
            frontmatter_overrides={"status": "supported", "evidence": ["[[research:s-2026-05-src]]"]},
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert any(
            "frontmatter wikilink" in f.message and "declares area 'research'" in f.message
            for f in findings
        )


# --- Rule 3: Backlink synchronization (fixup) ---

class TestRule03Backlinks:
    def test_writes_sidecars(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "concept", "x")
        write_kb_page(
            tmp_path, "areas/research", "finding", "y",
            body="Builds on [[c-2026-05-x]].",
        )

        findings = rule_03_backlinks.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

        # Sidecar for the finding should list the concept in links_out
        finding_sidecar = tmp_path / "areas/research/kb/findings/f-2026-05-y.md.links.json"
        assert finding_sidecar.is_file()
        import json
        data = json.loads(finding_sidecar.read_text())
        assert any("c-2026-05-x" in p for p in data["links_out"])

        # Sidecar for the concept should list the finding in links_in
        concept_sidecar = tmp_path / "areas/research/kb/concepts/c-2026-05-x.md.links.json"
        assert concept_sidecar.is_file()
        data = json.loads(concept_sidecar.read_text())
        assert any("f-2026-05-y" in p for p in data["links_in"])

    def test_prefixed_cross_area_link_creates_backlink(self, tmp_path: Path) -> None:
        """An area-prefixed cross-area link still resolves for backlink purposes."""
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/engineering", "finding", "thermal")
        write_kb_page(
            tmp_path, "areas/research", "finding", "cites-eng",
            body="See [[engineering:findings/f-2026-05-thermal]].",
        )
        findings = rule_03_backlinks.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []
        import json
        eng_sidecar = tmp_path / "areas/engineering/kb/findings/f-2026-05-thermal.md.links.json"
        assert eng_sidecar.is_file()
        data = json.loads(eng_sidecar.read_text())
        assert any("f-2026-05-cites-eng" in p for p in data["links_in"])


# --- Rule 5: Supersession integrity ---

class TestRule05Supersession:
    def test_superseded_without_replacement(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "finding", "old",
            frontmatter_overrides={"status": "superseded"},
        )
        findings = rule_05_supersession.check(tmp_path, DEFAULT_CONFIG)
        assert any("superseded_by is not populated" in f.message for f in findings)

    def test_link_to_superseded(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "new")
        write_kb_page(
            tmp_path, "areas/research", "finding", "old",
            frontmatter_overrides={"status": "superseded", "superseded_by": "[[f-2026-05-new]]"},
        )
        write_kb_page(
            tmp_path, "areas/research", "concept", "uses",
            body="Builds on [[f-2026-05-old]].",
        )
        findings = rule_05_supersession.check(tmp_path, DEFAULT_CONFIG)
        assert any("which is superseded" in f.message for f in findings)

    def test_clean_supersession(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "new")
        write_kb_page(
            tmp_path, "areas/research", "finding", "old",
            frontmatter_overrides={"status": "superseded", "superseded_by": "[[f-2026-05-new]]"},
        )
        findings = rule_05_supersession.check(tmp_path, DEFAULT_CONFIG)
        # No link-to-superseded; old has its replacement set
        assert findings == []


# --- Rule 6: Type-specific completeness ---

class TestRule06Completeness:
    def test_concept_under_test_needs_evidence(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "concept", "ut",
            frontmatter_overrides={"status": "under_test"},
        )
        findings = rule_06_completeness.check(tmp_path, DEFAULT_CONFIG)
        assert any("needs non-empty `evidence`" in f.message for f in findings)

    def test_concept_developing_no_evidence_ok(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "concept", "dev",
            frontmatter_overrides={"status": "developing"},
        )
        findings = rule_06_completeness.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_concept_supported_with_evidence_ok(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "concept", "ok",
            frontmatter_overrides={
                "status": "supported",
                "evidence": ["[[s-foo]]", "[[s-bar]]"],
            },
        )
        findings = rule_06_completeness.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_finding_needs_provenance(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Manually write a finding without provenance
        page = tmp_path / "areas/research/kb/findings/f-2026-05-noprov.md"
        page.parent.mkdir(parents=True)
        page.write_text(
            "---\n"
            "id: f-2026-05-noprov\ntitle: x\ntype: finding\nstatus: active\n"
            "area: research\ncreated: 2026-05-08\nupdated: 2026-05-08\nsummary: x\n"
            "---\n\nx\n"
        )
        findings = rule_06_completeness.check(tmp_path, DEFAULT_CONFIG)
        assert any("provenance" in f.message for f in findings)

    def test_decision_needs_alternatives_field(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        page = tmp_path / "areas/research/kb/decisions/d-2026-05-noalt.md"
        page.parent.mkdir(parents=True)
        page.write_text(
            "---\n"
            "id: d-2026-05-noalt\ntitle: x\ntype: decision\nstatus: active\n"
            "area: research\ncreated: 2026-05-08\nupdated: 2026-05-08\nsummary: x\n"
            "---\n\nx\n"
        )
        findings = rule_06_completeness.check(tmp_path, DEFAULT_CONFIG)
        assert any("alternatives_considered" in f.message for f in findings)


# --- Rule 7: Pulse size ---

class TestRule07PulseSize:
    def test_under_cap(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "commons" / "pulse.md").write_text("\n".join(["line"] * 50))
        findings = rule_07_pulse_size.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_over_cap(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "commons" / "pulse.md").write_text("\n".join(["line"] * 200))
        findings = rule_07_pulse_size.check(tmp_path, DEFAULT_CONFIG)
        assert any("exceeds line cap" in f.message for f in findings)

    def test_per_area_pulse(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area_pulse = tmp_path / "areas" / "research" / "pulse.md"
        area_pulse.parent.mkdir(parents=True)
        area_pulse.write_text("\n".join(["x"] * 200))
        findings = rule_07_pulse_size.check(tmp_path, DEFAULT_CONFIG)
        assert any("research/pulse.md" in f.file_path for f in findings)

    def test_custom_cap(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "commons" / "pulse.md").write_text("\n".join(["x"] * 30))
        # With cap of 20, should fire
        findings = rule_07_pulse_size.check(tmp_path, {"lint": {"pulse_line_cap": 20}})
        assert any("exceeds line cap" in f.message for f in findings)


# --- Rule 12: Data manifest integrity ---

class TestRule12Manifest:
    def _write_manifest(self, tmp_path: Path, **fm_overrides) -> Path:
        manifest_dir = tmp_path / "areas/research/data/manifests"
        manifest_dir.mkdir(parents=True)
        fm = {
            "id": "m-2026-05-test",
            "title": "Test",
            "type": "source",
            "status": "active",
            "area": "research",
            "created": "2026-05-08",
            "updated": "2026-05-08",
            "summary": "test manifest",
            "storage_uri": "s3://bucket/dataset",
            "provenance": {"kind": "internal-experiment"},
            "context_pages": ["[[c-foo]]"],
        }
        fm.update(fm_overrides)
        lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            elif isinstance(v, dict):
                lines.append(f"{k}:")
                for sk, sv in v.items():
                    lines.append(f"  {sk}: {sv}")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("body")
        path = manifest_dir / "m-2026-05-test.md"
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_valid_manifest(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._write_manifest(tmp_path)
        findings = rule_12_manifest.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_missing_storage_uri(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._write_manifest(tmp_path, storage_uri="")
        findings = rule_12_manifest.check(tmp_path, DEFAULT_CONFIG)
        assert any("storage_uri" in f.message for f in findings)

    def test_missing_context_pages(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._write_manifest(tmp_path, context_pages=[])
        findings = rule_12_manifest.check(tmp_path, DEFAULT_CONFIG)
        assert any("context_pages" in f.message for f in findings)


# --- Rule 15: Index maintenance (fixup) ---

class TestRule15Index:
    def test_generates_areas_index(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        # Add an area with a brief
        area = tmp_path / "areas" / "research"
        area.mkdir(parents=True)
        (area / "brief.md").write_text("# Research\n\nWe investigate optical noise.\n")

        findings = rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []
        idx = tmp_path / "areas-index.md"
        assert idx.is_file()
        content = idx.read_text()
        assert "research" in content
        assert "investigate optical noise" in content
        # Top-level area renders as h3 (### areas/research/), not h4 — no skipped
        # heading level under the ## commons heading.
        assert "### areas/research/" in content
        assert "#### areas/research/" not in content

    def test_sub_area_renders_one_level_deeper(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        sub = tmp_path / "areas" / "research" / "optics"
        sub.mkdir(parents=True)
        (tmp_path / "areas" / "research" / "brief.md").write_text("# Research\n\nParent.\n")
        (sub / "brief.md").write_text("# Optics\n\nSub-area.\n")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        content = (tmp_path / "areas-index.md").read_text()
        assert "### areas/research/" in content            # parent at h3
        assert "#### areas/research/optics/" in content     # sub-area at h4

    def test_generates_kb_index(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "shot-noise")
        write_kb_page(
            tmp_path, "areas/research", "concept", "ut1",
            frontmatter_overrides={
                "status": "under_test",
                "evidence": ["[[s-1]]"],
            },
        )

        findings = rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []
        kb_index = tmp_path / "areas/research/kb/index.md"
        assert kb_index.is_file()
        content = kb_index.read_text()
        assert "Findings" in content
        assert "Concepts under test" in content
        assert "f-2026-05-shot-noise" in content
        assert "c-2026-05-ut1" in content

    def test_index_stamp_does_not_move_backwards(self, tmp_path: Path) -> None:
        """Rule 15 keeps a newer existing stamp instead of rolling it back (5h)."""
        make_minimal_repo(tmp_path)
        idx = tmp_path / "areas-index.md"
        idx.write_text(
            "# Areas Index\n\n_Auto-maintained by lint; do not edit by hand._\n"
            "_Last regenerated: 2999-01-01_\n\n"
        )
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "_Last regenerated: 2999-01-01_" in idx.read_text()


# --- Rule 18: ID uniqueness across the project ---

class TestRule18IdUniqueness:
    def test_unique_ids_pass(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "alpha")
        write_kb_page(tmp_path, "areas/research", "finding", "beta")
        write_kb_page(tmp_path, "areas/business-model", "finding", "gamma")
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_same_id_in_two_areas_flagged(self, tmp_path: Path) -> None:
        """Two pages with the same id in different areas — the bug shape."""
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "shared-slug")
        write_kb_page(tmp_path, "areas/business-model", "finding", "shared-slug")
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        # Each colliding file produces a finding so the user sees the issue
        # from either entry point
        assert len(findings) == 2
        # Both findings mention the duplicated id
        for f in findings:
            assert "f-2026-05-shared-slug" in f.message
            assert "2 pages" in f.message

    def test_area_and_commons_id_collision_flagged(self, tmp_path: Path) -> None:
        """The specific bug shape: source area page + commons page sharing id."""
        make_minimal_repo(tmp_path)
        # Area page (the source of a promotion that incorrectly kept its id)
        write_kb_page(tmp_path, "areas/research", "finding", "shot-noise")
        # Commons page with the same id (what the buggy /promote produced)
        commons_dir = tmp_path / "commons" / "kb" / "findings"
        commons_dir.mkdir(parents=True, exist_ok=True)
        (commons_dir / "f-2026-05-shot-noise.md").write_text(
            "---\n"
            "id: f-2026-05-shot-noise\n"
            "title: x\ntype: finding\nstatus: active\narea: commons\n"
            "created: 2026-05-08\nupdated: 2026-05-08\n"
            "summary: x\n"
            "provenance:\n  kind: external\n  ref: x\n  raw_path: '~'\n"
            "evidence: [x]\nconfidence: high\n"
            "---\n\nBody.\n"
        )
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        assert len(findings) == 2
        # The suggestion points at the commons rename convention
        for f in findings:
            assert "commons-" in f.suggestion

    def test_correctly_promoted_pages_pass(self, tmp_path: Path) -> None:
        """Area + commons with distinct ids (the fix's expected state) is clean."""
        make_minimal_repo(tmp_path)
        # Area source page
        write_kb_page(tmp_path, "areas/research", "finding", "shot-noise")
        # Commons page using the new commons-id convention
        commons_dir = tmp_path / "commons" / "kb" / "findings"
        commons_dir.mkdir(parents=True, exist_ok=True)
        (commons_dir / "f-commons-shot-noise.md").write_text(
            "---\n"
            "id: f-commons-shot-noise\n"
            "title: x\ntype: finding\nstatus: active\narea: commons\n"
            "created: 2026-05-08\nupdated: 2026-05-08\n"
            "summary: x\n"
            "provenance:\n  kind: external\n  ref: x\n  raw_path: '~'\n"
            "evidence: [x]\nconfidence: high\n"
            "---\n\nBody.\n"
        )
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []

    def test_three_way_collision(self, tmp_path: Path) -> None:
        """A 3+ way collision is reported on every involved file."""
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "x")
        write_kb_page(tmp_path, "areas/business-model", "finding", "x")
        write_kb_page(tmp_path, "areas/frontend", "finding", "x")
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        assert len(findings) == 3
        for f in findings:
            assert "3 pages" in f.message

    def test_missing_id_field_ignored(self, tmp_path: Path) -> None:
        """A page missing an id is Rule 1's problem, not Rule 18's."""
        make_minimal_repo(tmp_path)
        # Two pages, both missing id — should not be flagged as collisions
        # (they're flagged by Rule 1 separately)
        for name in ("a", "b"):
            path = tmp_path / "areas/research/kb/findings" / f"f-2026-05-{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("---\ntitle: x\ntype: finding\n---\n\nBody.\n")
        findings = rule_18_id_uniqueness.check(tmp_path, DEFAULT_CONFIG)
        assert findings == []


# --- Rule 20: Commons drift (warning; self-gating) ---

_ON_10 = {"lint": {"warnings_visible": {"rule_10_promotion_freshness": True},
                   "promotion_freshness_active_days": 14}}


class TestRule10PromotionFreshness:
    def _commons_page(self, tmp_path: Path, *, human_reviewed, promoted_on) -> None:
        make_minimal_repo(tmp_path)
        cdir = tmp_path / "commons/kb/findings"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "f-commons-x.md").write_text(
            "---\nid: f-commons-x\ntitle: X\ntype: finding\nstatus: active\n"
            "area: commons\ncreated: 2026-05-01\nupdated: 2026-05-01\nsummary: X.\n"
            f"human_reviewed: {human_reviewed}\npromoted_on: {promoted_on}\n---\n\nBody.\n"
        )

    def test_disabled_by_default(self, tmp_path: Path) -> None:
        self._commons_page(tmp_path, human_reviewed="false", promoted_on="2020-01-01")
        from lint_rules import rule_10_promotion_freshness
        assert rule_10_promotion_freshness.check(tmp_path, DEFAULT_CONFIG) == []

    def test_flags_overdue_unreviewed(self, tmp_path: Path) -> None:
        # promoted long ago (non-git tmp repo → calendar-day fallback), still unreviewed
        self._commons_page(tmp_path, human_reviewed="false", promoted_on="2020-01-01")
        from lint_rules import rule_10_promotion_freshness
        findings = rule_10_promotion_freshness.check(tmp_path, _ON_10)
        assert len(findings) == 1
        assert "human_reviewed: false" in findings[0].message

    def test_reviewed_page_not_flagged(self, tmp_path: Path) -> None:
        self._commons_page(tmp_path, human_reviewed="true", promoted_on="2020-01-01")
        from lint_rules import rule_10_promotion_freshness
        assert rule_10_promotion_freshness.check(tmp_path, _ON_10) == []

    def test_fresh_promotion_not_flagged(self, tmp_path: Path) -> None:
        today = date.today().isoformat()
        self._commons_page(tmp_path, human_reviewed="false", promoted_on=today)
        from lint_rules import rule_10_promotion_freshness
        assert rule_10_promotion_freshness.check(tmp_path, _ON_10) == []


_ON_20 = {"lint": {"warnings_visible": {"rule_20_commons_drift": True}}}


class TestRule20CommonsDrift:
    def _setup(self, tmp_path: Path, aligned_on: str, src_updated: str) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "areas/research", "finding", "src",
            frontmatter_overrides={"updated": src_updated},
        )  # id f-2026-05-src
        cdir = tmp_path / "commons/kb/findings"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "f-commons-src.md").write_text(
            "---\nid: f-commons-src\ntitle: Src\ntype: finding\nstatus: active\n"
            "area: commons\ncreated: 2026-05-01\nupdated: 2026-05-01\nsummary: S.\n"
            f"promoted_from_page: f-2026-05-src\naligned_on: {aligned_on}\n---\n\nBody.\n"
        )

    def test_disabled_by_default(self, tmp_path: Path) -> None:
        self._setup(tmp_path, "2026-05-01", "2026-05-08")
        assert rule_20_commons_drift.check(tmp_path, DEFAULT_CONFIG) == []

    def test_flags_drift_when_source_newer(self, tmp_path: Path) -> None:
        self._setup(tmp_path, "2026-05-01", "2026-05-08")
        findings = rule_20_commons_drift.check(tmp_path, _ON_20)
        assert any("changed on 2026-05-08" in f.message for f in findings)

    def test_no_drift_when_aligned_after_source(self, tmp_path: Path) -> None:
        self._setup(tmp_path, "2026-05-10", "2026-05-08")
        assert rule_20_commons_drift.check(tmp_path, _ON_20) == []

    def _write_commons(self, tmp_path: Path, extra_fm: str) -> None:
        """Write a commons page with the given extra frontmatter lines (no
        source page). Used for the un-checkable cases."""
        make_minimal_repo(tmp_path)
        cdir = tmp_path / "commons/kb/findings"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "f-commons-x.md").write_text(
            "---\nid: f-commons-x\ntitle: X\ntype: finding\nstatus: active\n"
            "area: commons\ncreated: 2026-05-01\nupdated: 2026-05-01\nsummary: X.\n"
            f"{extra_fm}---\n\nBody.\n"
        )

    def test_flags_page_missing_promoted_from_page(self, tmp_path: Path) -> None:
        """A commons page with no source link is surfaced, not silently skipped
        (dogfood item 1: silent skip is a false negative)."""
        self._write_commons(tmp_path, "aligned_on: 2026-05-01\n")
        findings = rule_20_commons_drift.check(tmp_path, _ON_20)
        assert len(findings) == 1
        assert "no `promoted_from_page`" in findings[0].message

    def test_flags_page_missing_aligned_on(self, tmp_path: Path) -> None:
        """The reported case: pre-migration pages lack aligned_on and must be
        surfaced rather than covered by a misleading `lint: clean`."""
        self._write_commons(tmp_path, "promoted_from_page: f-2026-05-src\n")
        findings = rule_20_commons_drift.check(tmp_path, _ON_20)
        assert len(findings) == 1
        assert "missing `aligned_on`" in findings[0].message

    def test_flags_page_with_dangling_source(self, tmp_path: Path) -> None:
        """promoted_from_page points at a source that isn't in the kb → still
        un-checkable, still surfaced."""
        self._write_commons(
            tmp_path, "promoted_from_page: f-2026-05-missing\naligned_on: 2026-05-01\n"
        )
        findings = rule_20_commons_drift.check(tmp_path, _ON_20)
        assert len(findings) == 1
        assert "not found in the kb" in findings[0].message


# --- Rule 21: Commons twin-link preference (warning; self-gating) ---

_ON_21 = {"lint": {"warnings_visible": {"rule_21_commons_twin_links": True}}}


class TestRule21CommonsTwinLinks:
    def _twin(self, tmp_path: Path) -> None:
        write_kb_page(tmp_path, "areas/research", "concept", "foo")  # c-2026-05-foo
        cc = tmp_path / "commons/kb/concepts"
        cc.mkdir(parents=True, exist_ok=True)
        (cc / "c-commons-foo.md").write_text(
            "---\nid: c-commons-foo\ntitle: Foo\ntype: concept\nstatus: supported\n"
            "area: commons\ncreated: 2026-05-01\nupdated: 2026-05-01\nsummary: F.\n"
            "promoted_from_page: c-2026-05-foo\n---\n\nBody.\n"
        )

    def _commons_citing(self, tmp_path: Path, target: str) -> None:
        cf = tmp_path / "commons/kb/findings"
        cf.mkdir(parents=True, exist_ok=True)
        (cf / "f-commons-bar.md").write_text(
            "---\nid: f-commons-bar\ntitle: Bar\ntype: finding\nstatus: active\n"
            "area: commons\ncreated: 2026-05-01\nupdated: 2026-05-01\nsummary: B.\n"
            f"promoted_from_page: f-2026-05-bar\n---\n\nBuilds on [[{target}]].\n"
        )

    def test_disabled_by_default(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._twin(tmp_path)
        self._commons_citing(tmp_path, "c-2026-05-foo")
        assert rule_21_commons_twin_links.check(tmp_path, DEFAULT_CONFIG) == []

    def test_flags_citation_to_area_page_with_twin(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._twin(tmp_path)
        self._commons_citing(tmp_path, "c-2026-05-foo")
        findings = rule_21_commons_twin_links.check(tmp_path, _ON_21)
        assert any(
            "prefer the twin" in f.message and "c-commons-foo" in f.message
            for f in findings
        )

    def test_no_flag_when_already_citing_twin(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        self._twin(tmp_path)
        self._commons_citing(tmp_path, "c-commons-foo")
        assert rule_21_commons_twin_links.check(tmp_path, _ON_21) == []

    def test_no_flag_for_area_page_without_twin(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "concept", "notwin")
        self._commons_citing(tmp_path, "c-2026-05-notwin")
        assert rule_21_commons_twin_links.check(tmp_path, _ON_21) == []
