"""
Tests for _framework/tools/framework.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from framework import (
    apply_plan,
    format_status,
    insert_capability_section,
    plan_disable,
    plan_disable_lint,
    plan_enable,
    plan_enable_lint,
    remove_capability_section,
    status,
    _extract_preload_sections,
    _insert_role_block,
    _remove_role_block,
)

from lint_helpers import make_minimal_repo


# --- Test fixtures ---

def _write_basic_repo(tmp_path: Path) -> Path:
    """Build a minimal repo with CLAUDE.md, the snippet files, an area, and a role."""
    make_minimal_repo(tmp_path)

    # CLAUDE.md
    (tmp_path / "CLAUDE.md").write_text(textwrap.dedent("""
        # Project operating manual

        ## What this project is

        See `commons/brief.md`.

        ## Frontmatter discipline

        See _framework/schema/frontmatter.md.

        ## Pulse discipline

        Append events to _journal/pulse.log.

        ## Spec lifecycle

        brief → plan → tasks → outcome.

        ## Skills

        See _framework/schema/capabilities.md.

        ## Escalation triggers

        When to stop and ask the human:
        - Two findings contradict.
    """).strip() + "\n")

    # Snippets
    snippets_dir = tmp_path / "_framework" / "schema" / "claude-snippets"
    snippets_dir.mkdir(parents=True)
    (snippets_dir / "multi_area.md").write_text(
        "## Cross-area reads\n\nWhen multi_area is enabled, prefer /exchange.\n"
    )
    (snippets_dir / "por.md").write_text(
        "## POR discipline\n\nUpdate POR when phases shift.\n"
    )
    (snippets_dir / "task_subagents.md").write_text(
        "## Subagent pattern\n\nWhen task_subagents is enabled, /implement spawns subagents.\n"
    )
    (snippets_dir / "formal_review.md").write_text(
        "## Formal review\n\nReviewer subagents read against the spec.\n"
    )

    # An area with a brief and a role
    area = tmp_path / "areas" / "research"
    area.mkdir(parents=True)
    (area / "brief.md").write_text("# research\n\nresearch area\n")
    (area / "pulse.md").write_text("# research — pulse\n")

    role_dir = area / "roles" / "researcher"
    role_dir.mkdir(parents=True)
    (role_dir / "role.md").write_text(textwrap.dedent("""
        ---
        role: researcher
        area: research
        summary: research role
        ---

        # researcher

        ## Preload context (full)

        Schema:
        1. /CLAUDE.md
        2. /_framework/schema/frontmatter.md

        Project and area:
        3. /commons/brief.md
        4. /commons/pulse.md
        5. /areas/research/brief.md
        6. /areas/research/pulse.md
        7. /areas/research/kb/index.md

        ## Preload context (frontmatter only)

        Patterns:
        - /areas/research/kb/

        ## Operating boundaries

        - Writes allowed: /areas/research/** except /areas/research/raw/**.
        - Reads allowed: full repo.

        ## Allowed skills

        start, ingest, ask, plan, implement, replan, wrap-up, check, propose-promotion, promote, framework

        ## Default behaviors

        - Cite using [[wikilinks]].
        - Ask the human when uncertain.
    """).strip() + "\n")

    return tmp_path


def _load_config(tmp_path: Path) -> dict:
    config_path = tmp_path / "_framework" / "config.yml"
    return yaml.safe_load(config_path.read_text())


# --- CLAUDE.md splicing ---

class TestClaudeMdSplicing:
    def test_insert_creates_block_with_markers(self) -> None:
        original = "# Project\n\n## Skills\n\nfoo\n\n## Escalation triggers\n\nask.\n"
        result = insert_capability_section(original, "multi_area", "## Cross-area reads\n\nbody.")
        assert "<!-- begin capability: multi_area -->" in result
        assert "<!-- end capability: multi_area -->" in result
        # Inserted before "## Escalation triggers"
        assert result.find("multi_area") < result.find("Escalation triggers")

    def test_insert_replaces_existing_block(self) -> None:
        original = (
            "# Project\n\n"
            "<!-- begin capability: multi_area -->\n"
            "## Cross-area reads\n\nold body.\n"
            "<!-- end capability: multi_area -->\n\n"
            "## Escalation triggers\n\nask.\n"
        )
        result = insert_capability_section(original, "multi_area", "## Cross-area reads\n\nnew body.")
        # New body present
        assert "new body" in result
        # Old body gone
        assert "old body" not in result
        # Only one set of markers
        assert result.count("<!-- begin capability: multi_area -->") == 1

    def test_remove_strips_block(self) -> None:
        original = (
            "# Project\n\n"
            "<!-- begin capability: por -->\n"
            "## POR discipline\n\nbody.\n"
            "<!-- end capability: por -->\n\n"
            "## Escalation triggers\n\nask.\n"
        )
        result = remove_capability_section(original, "por")
        assert "<!-- begin capability: por -->" not in result
        assert "POR discipline" not in result
        assert "Escalation triggers" in result

    def test_remove_no_op_when_absent(self) -> None:
        original = "# Project\n\n## Escalation triggers\n"
        result = remove_capability_section(original, "por")
        assert result == original


# --- Role file editing ---

class TestRoleFileEditing:
    def test_insert_block_in_section(self) -> None:
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md
            2. /commons/brief.md

            ## Operating boundaries

            - Reads allowed: full repo.
        """).strip()
        result = _insert_role_block(role_text, "Preload context (full)", "por", ["- /commons/POR.md"])
        assert "# capability: por" in result
        assert "# end capability: por" in result
        assert "/commons/POR.md" in result
        # The por block should be inside the Preload section, before the next ##
        por_idx = result.find("# capability: por")
        boundaries_idx = result.find("## Operating boundaries")
        assert por_idx < boundaries_idx

    def test_insert_idempotent(self) -> None:
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md

            ## Operating boundaries

            - x
        """).strip()
        once = _insert_role_block(role_text, "Preload context (full)", "por", ["- /commons/POR.md"])
        twice = _insert_role_block(once, "Preload context (full)", "por", ["- /commons/POR.md"])
        assert once == twice  # Second insert is a no-op

    def test_remove_block(self) -> None:
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md

            # capability: por
            - /commons/POR.md
            # end capability: por

            ## Operating boundaries
        """).strip()
        result = _remove_role_block(role_text, "por")
        assert "# capability: por" not in result
        assert "/commons/POR.md" not in result
        assert "## Preload context (full)" in result
        assert "## Operating boundaries" in result

    def test_remove_no_op_when_absent(self) -> None:
        role_text = "## Preload context (full)\n\n1. /CLAUDE.md\n"
        result = _remove_role_block(role_text, "por")
        assert result == role_text

    def test_extract_preload_sections(self) -> None:
        text = textwrap.dedent("""
            ---
            role: x
            ---

            ## Preload context (full)

            1. /CLAUDE.md
            2. /commons/brief.md

            ## Preload context (frontmatter only)

            - /commons/kb/findings/

            ## Operating boundaries

            - x
        """).strip()
        sections = _extract_preload_sections(text)
        assert any("/CLAUDE.md" in line for line in sections["full"])
        assert any("/commons/kb/findings/" in line for line in sections["frontmatter"])
        # Operating boundaries is NOT a preload section
        assert not any("Operating boundaries" in line for line in sections["full"])


# --- plan_enable (per capability) ---

class TestPlanEnable:
    def test_unknown_capability(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable("bogus", tmp_path, config)
        assert plan.error is not None
        assert "unknown" in plan.error

    def test_already_enabled_no_op(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        config["capabilities"]["multi_area"] = True
        plan = plan_enable("multi_area", tmp_path, config)
        assert plan.changes == []
        assert any("already enabled" in w for w in plan.warnings)

    def test_multi_area_changes(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable("multi_area", tmp_path, config)
        # Should change CLAUDE.md and the role file
        changed_paths = [c.path for c in plan.changes]
        assert "CLAUDE.md" in changed_paths
        assert any("role.md" in p for p in changed_paths)
        # config update reflects new state
        assert plan.config_updates == {"capabilities.multi_area": True}

    def test_por_creates_files(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable("por", tmp_path, config)
        creates = [c for c in plan.changes if c.kind == "create"]
        created_paths = {c.path for c in creates}
        assert "commons/POR.md" in created_paths
        assert "areas/research/POR.md" in created_paths
        assert "commons/roles/coordinator/role.md" in created_paths

    def test_formal_review_requires_task_subagents(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        # task_subagents is OFF in default config
        plan = plan_enable("formal_review", tmp_path, config)
        assert plan.error == "unmet dependency"
        assert any("task_subagents" in w for w in plan.warnings)

    def test_formal_review_when_task_subagents_on(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        config["capabilities"]["task_subagents"] = True
        plan = plan_enable("formal_review", tmp_path, config)
        assert plan.error is None
        # Should create a reviewer role variant
        creates = [c for c in plan.changes if c.kind == "create"]
        assert any("researcher-reviewer" in c.path for c in creates)

    def test_task_subagents_only_changes_claude_md(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable("task_subagents", tmp_path, config)
        # Only CLAUDE.md should be edited; no role file changes
        edited_role_files = [c for c in plan.changes if "role.md" in c.path]
        assert edited_role_files == []
        assert any(c.path == "CLAUDE.md" for c in plan.changes)


# --- plan_disable ---

class TestPlanDisable:
    def test_already_disabled_no_op(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_disable("multi_area", tmp_path, config)
        assert plan.changes == []

    def test_disable_blocked_by_dependent(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        config["capabilities"]["task_subagents"] = True
        config["capabilities"]["formal_review"] = True
        plan = plan_disable("task_subagents", tmp_path, config)
        assert plan.error is not None
        assert "formal_review" in plan.error


# --- apply_plan ---

class TestApplyPlan:
    def test_enable_multi_area_end_to_end(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable("multi_area", tmp_path, config)
        apply_plan(plan, tmp_path)

        # CLAUDE.md updated
        claude_md = (tmp_path / "CLAUDE.md").read_text()
        assert "<!-- begin capability: multi_area -->" in claude_md
        assert "Cross-area reads" in claude_md

        # Role file updated
        role_text = (tmp_path / "areas/research/roles/researcher/role.md").read_text()
        assert "# capability: multi_area" in role_text
        assert "exchange" in role_text

        # Config updated
        new_config = _load_config(tmp_path)
        assert new_config["capabilities"]["multi_area"] is True

    def test_enable_then_disable_roundtrip(self, tmp_path: Path) -> None:
        """Enabling then disabling should restore the original state (modulo dates)."""
        _write_basic_repo(tmp_path)
        original_claude = (tmp_path / "CLAUDE.md").read_text()
        original_role = (tmp_path / "areas/research/roles/researcher/role.md").read_text()

        config = _load_config(tmp_path)
        apply_plan(plan_enable("multi_area", tmp_path, config), tmp_path)

        config = _load_config(tmp_path)
        apply_plan(plan_disable("multi_area", tmp_path, config), tmp_path)

        # CLAUDE.md should have no capability markers
        claude_md_after = (tmp_path / "CLAUDE.md").read_text()
        assert "<!-- begin capability: multi_area -->" not in claude_md_after
        assert "Cross-area reads" not in claude_md_after

        # Role file should have no capability markers
        role_text_after = (tmp_path / "areas/research/roles/researcher/role.md").read_text()
        assert "# capability: multi_area" not in role_text_after

        # Config restored
        new_config = _load_config(tmp_path)
        assert new_config["capabilities"]["multi_area"] is False

    def test_enable_por_creates_files(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        apply_plan(plan_enable("por", tmp_path, config), tmp_path)

        assert (tmp_path / "commons" / "POR.md").is_file()
        assert (tmp_path / "areas" / "research" / "POR.md").is_file()
        assert (tmp_path / "commons" / "roles" / "coordinator" / "role.md").is_file()

        # POR entries appear in the researcher role's preload
        role_text = (tmp_path / "areas/research/roles/researcher/role.md").read_text()
        assert "/commons/POR.md" in role_text
        assert "/areas/research/POR.md" in role_text

    def test_disable_por_keeps_por_files_removes_coordinator(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        apply_plan(plan_enable("por", tmp_path, config), tmp_path)

        # Confirm POR files and coordinator exist
        assert (tmp_path / "commons" / "POR.md").is_file()
        assert (tmp_path / "commons" / "roles" / "coordinator" / "role.md").is_file()

        config = _load_config(tmp_path)
        apply_plan(plan_disable("por", tmp_path, config), tmp_path)

        # POR files persist
        assert (tmp_path / "commons" / "POR.md").is_file()
        assert (tmp_path / "areas" / "research" / "POR.md").is_file()
        # Coordinator role is removed (and its dir too)
        assert not (tmp_path / "commons" / "roles" / "coordinator" / "role.md").exists()

        # Role file POR entries removed
        role_text = (tmp_path / "areas/research/roles/researcher/role.md").read_text()
        assert "/commons/POR.md" not in role_text

    def test_formal_review_creates_and_removes_reviewer_roles(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        config["capabilities"]["task_subagents"] = True
        # Persist updated config so subsequent reads see it
        (tmp_path / "_framework" / "config.yml").write_text(yaml.safe_dump(config))

        apply_plan(plan_enable("formal_review", tmp_path, config), tmp_path)
        assert (tmp_path / "areas/research/roles/researcher-reviewer/role.md").is_file()

        # Implementer role gained `review` skill
        role_text = (tmp_path / "areas/research/roles/researcher/role.md").read_text()
        assert "# capability: formal_review" in role_text
        assert "review" in role_text.split("# capability: formal_review")[1].split("# end capability: formal_review")[0]

        # Now disable
        config = _load_config(tmp_path)
        apply_plan(plan_disable("formal_review", tmp_path, config), tmp_path)
        assert not (tmp_path / "areas/research/roles/researcher-reviewer/role.md").exists()


# --- Lint visibility ---

class TestLintVisibility:
    def test_enable_lint_rule(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable_lint("rule_20_commons_drift", tmp_path, config)
        assert plan.config_updates == {"lint.warnings_visible.rule_20_commons_drift": True}
        apply_plan(plan, tmp_path)

        new_config = _load_config(tmp_path)
        assert new_config["lint"]["warnings_visible"]["rule_20_commons_drift"] is True

    def test_enable_lint_accepts_short_form(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable_lint("20", tmp_path, config)
        assert plan.config_updates == {"lint.warnings_visible.rule_20_commons_drift": True}

    def test_disable_lint_rule(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        # First enable
        apply_plan(plan_enable_lint("rule_20_commons_drift", tmp_path, config), tmp_path)
        config = _load_config(tmp_path)
        # Then disable
        plan = plan_disable_lint("rule_20_commons_drift", tmp_path, config)
        apply_plan(plan, tmp_path)
        new_config = _load_config(tmp_path)
        assert new_config["lint"]["warnings_visible"]["rule_20_commons_drift"] is False

    def test_unknown_lint_rule(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable_lint("rule_99_imaginary", tmp_path, config)
        assert plan.error is not None
        assert "unknown" in plan.error

    def test_configurable_set_derived_from_shipped_rules(self) -> None:
        """Regression: the configurable set is derived from the shipped warning
        modules, not hardcoded — so a rule that ships is en-/disable-able and a
        phantom (unimplemented) rule is not. This is the bug that let rules 20/21
        ship while enable-lint still rejected them."""
        from framework import CONFIGURABLE_LINT_RULES
        # Shipped self-gating warning rules are present.
        assert "rule_20_commons_drift" in CONFIGURABLE_LINT_RULES
        assert "rule_21_commons_twin_links" in CONFIGURABLE_LINT_RULES
        # Error rules (no CONFIG_KEY) are never configurable.
        assert "rule_18_id_uniqueness" not in CONFIGURABLE_LINT_RULES
        # Unimplemented "planned" rules are not silently accepted.
        assert "rule_4_orphans" not in CONFIGURABLE_LINT_RULES

    def test_enable_lint_rejects_phantom_rule(self, tmp_path: Path) -> None:
        """A planned-but-unimplemented rule is rejected, not silently written."""
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        plan = plan_enable_lint("rule_4_orphans", tmp_path, config)
        assert plan.error is not None
        assert "unknown" in plan.error


# --- Status ---

class TestStatus:
    def test_status_reports_capabilities(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        state = status(tmp_path, config)
        assert "multi_area" in state["capabilities"]
        assert state["capabilities"]["multi_area"] is False
        assert "rule_20_commons_drift" in state["lint_warnings_visible"]

    def test_format_status_renders(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        state = status(tmp_path, config)
        report = format_status(state)
        assert "Capabilities:" in report
        assert "multi_area" in report


# --- Prune ---

from framework import (  # noqa: E402
    PruneCandidate,
    find_prune_candidates,
    format_prune_candidates,
    plan_prune,
    _remove_preload_line,
)
from telemetry import session_end, session_start  # noqa: E402


def _write_kb_finding_for_prune(tmp_path: Path, slug: str, status: str = "active") -> Path:
    """Write a finding page under areas/research/kb/findings/."""
    kb = tmp_path / "areas" / "research" / "kb" / "findings"
    kb.mkdir(parents=True, exist_ok=True)
    page_id = f"f-2026-05-{slug}"
    path = kb / f"{page_id}.md"
    path.write_text(textwrap.dedent(f"""
        ---
        id: {page_id}
        title: {slug}
        type: finding
        status: {status}
        area: research
        created: 2026-05-08
        updated: 2026-05-08
        summary: test
        provenance:
          kind: experiment
        ---

        Body.
    """).strip() + "\n")
    return path


def _add_role_preload_entries(role_path: Path, lines: list[str]) -> None:
    """Append entries to the role file's "Preload context (full)" section."""
    text = role_path.read_text(encoding="utf-8")
    insertion = "\n".join(lines)
    # Insert before the next ##
    new_text = text.replace(
        "## Preload context (frontmatter only)",
        f"{insertion}\n\n## Preload context (frontmatter only)",
        1,
    )
    role_path.write_text(new_text, encoding="utf-8")


class TestRemovePreloadLine:
    def test_removes_full_tier_entry(self) -> None:
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md
            2. /commons/brief.md
            3. /areas/research/kb/findings/f-2026-05-x.md

            ## Preload context (frontmatter only)

            - /areas/research/kb/
        """).strip() + "\n"
        new_text, removed = _remove_preload_line(
            role_text, "/areas/research/kb/findings/f-2026-05-x.md", tier="full"
        )
        assert removed is True
        assert "f-2026-05-x.md" not in new_text
        assert "/CLAUDE.md" in new_text  # untouched
        assert "/areas/research/kb/" in new_text  # untouched

    def test_removes_frontmatter_pattern(self) -> None:
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md

            ## Preload context (frontmatter only)

            - /areas/research/kb/findings/
            - /commons/kb/decisions/
        """).strip() + "\n"
        new_text, removed = _remove_preload_line(
            role_text, "/areas/research/kb/findings/", tier="frontmatter"
        )
        assert removed is True
        assert "/areas/research/kb/findings/" not in new_text
        assert "/commons/kb/decisions/" in new_text

    def test_skips_capability_block(self) -> None:
        """Entries inside a # capability: block must not be removed."""
        role_text = textwrap.dedent("""
            ## Preload context (full)

            1. /CLAUDE.md

            # capability: por
            - /commons/POR.md
            # end capability: por

            ## Preload context (frontmatter only)

            - /areas/research/kb/
        """).strip() + "\n"
        new_text, removed = _remove_preload_line(role_text, "/commons/POR.md", tier="full")
        assert removed is False  # capability block protected the line
        assert "/commons/POR.md" in new_text  # still present


class TestFindPruneCandidates:
    def test_lifecycle_dropped_page_flagged(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        # Add a finding with status: dropped
        dropped = _write_kb_finding_for_prune(tmp_path, "old", status="dropped")
        # Add it to the researcher role's preload
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        _add_role_preload_entries(role_path, [
            "Findings:",
            "8. /areas/research/kb/findings/f-2026-05-old.md",
        ])
        config = _load_config(tmp_path)
        candidates = find_prune_candidates(tmp_path, config)
        assert any(
            c.preload_path == "/areas/research/kb/findings/f-2026-05-old.md"
            and c.reason.startswith("target page has status 'dropped'")
            for c in candidates
        )

    def test_lifecycle_active_page_not_flagged(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        _write_kb_finding_for_prune(tmp_path, "fresh", status="active")
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        _add_role_preload_entries(role_path, [
            "8. /areas/research/kb/findings/f-2026-05-fresh.md",
        ])
        config = _load_config(tmp_path)
        candidates = find_prune_candidates(tmp_path, config)
        # An active page may show up as activity-stale (no sessions yet),
        # but should NOT be flagged for lifecycle reasons.
        lifecycle_flags = [c for c in candidates if "status" in c.reason]
        assert all(
            c.preload_path != "/areas/research/kb/findings/f-2026-05-fresh.md"
            for c in lifecycle_flags
        )

    def test_role_filter(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        _write_kb_finding_for_prune(tmp_path, "old", status="superseded")
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        _add_role_preload_entries(role_path, [
            "8. /areas/research/kb/findings/f-2026-05-old.md",
        ])
        config = _load_config(tmp_path)
        # Should match researcher
        candidates = find_prune_candidates(tmp_path, config, role_filter="researcher")
        assert len(candidates) >= 1
        # Should NOT match anything when filtering for a non-existent role
        none_candidates = find_prune_candidates(tmp_path, config, role_filter="nobody")
        assert none_candidates == []

    def test_capability_managed_entry_marked(self, tmp_path: Path) -> None:
        """An entry inside a # capability: block should be flagged with in_capability_block=True."""
        _write_basic_repo(tmp_path)
        # Add a finding with status: dropped, but place it inside a capability block
        _write_kb_finding_for_prune(tmp_path, "old", status="dropped")
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        text = role_path.read_text()
        # Inject a capability block with the dropped page
        new_text = text.replace(
            "## Preload context (frontmatter only)",
            "# capability: por\n- /areas/research/kb/findings/f-2026-05-old.md\n# end capability: por\n\n## Preload context (frontmatter only)",
            1,
        )
        role_path.write_text(new_text)
        config = _load_config(tmp_path)
        candidates = find_prune_candidates(tmp_path, config)
        relevant = [c for c in candidates if "f-2026-05-old" in c.preload_path]
        assert len(relevant) == 1
        assert relevant[0].in_capability_block is True

    def test_activity_threshold_requires_enough_sessions(self, tmp_path: Path) -> None:
        """With <N sessions of history, no activity-based candidates are produced."""
        _write_basic_repo(tmp_path)
        # No telemetry events at all
        config = _load_config(tmp_path)
        # Lower threshold so this is a meaningful test
        config.setdefault("prune", {})
        config["prune"]["full_tier_stale_sessions"] = 5
        candidates = find_prune_candidates(tmp_path, config)
        activity_flags = [c for c in candidates if "not cited" in c.reason]
        assert activity_flags == []  # insufficient history

    def test_activity_stale_full_entry_flagged(self, tmp_path: Path) -> None:
        """When enough sessions exist and an entry was never cited, flag it."""
        _write_basic_repo(tmp_path)
        # Lower threshold so we don't need many fake sessions
        config = _load_config(tmp_path)
        config.setdefault("prune", {})
        config["prune"]["full_tier_stale_sessions"] = 2

        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        # Stage 2 session_start+session_end pairs where this role is named.
        # First, record session_start using the role file
        import time
        for i in range(2):
            session_start(role_path, tmp_path)
            time.sleep(1)  # ensure distinct session_ids
            session_end(tmp_path, pages_cited=["/areas/research/kb/findings/f-2026-05-other.md"])
            time.sleep(1)
        # Now CLAUDE.md was preloaded both times but never cited.
        candidates = find_prune_candidates(tmp_path, config)
        # Should flag /CLAUDE.md as activity-stale
        activity_flags = [
            c for c in candidates
            if "not cited" in c.reason and c.role_name == "researcher"
        ]
        assert any("/CLAUDE.md" in c.preload_path for c in activity_flags)

    def test_cited_path_normalized_to_match_preload(self, tmp_path: Path) -> None:
        """Citation paths get normalized so they match preload entries with leading slashes."""
        _write_basic_repo(tmp_path)
        config = _load_config(tmp_path)
        config.setdefault("prune", {})
        config["prune"]["full_tier_stale_sessions"] = 2

        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        import time
        for _ in range(2):
            session_start(role_path, tmp_path)
            time.sleep(1)
            # Cite without leading slash — should still match /CLAUDE.md preload
            session_end(tmp_path, pages_cited=["CLAUDE.md"])
            time.sleep(1)
        candidates = find_prune_candidates(tmp_path, config)
        # /CLAUDE.md was cited (just without leading slash), so it should NOT be flagged
        assert not any(
            "/CLAUDE.md" in c.preload_path and "not cited" in c.reason
            for c in candidates
        )


class TestPlanPrune:
    def test_applies_remove_for_one_role(self, tmp_path: Path) -> None:
        _write_basic_repo(tmp_path)
        _write_kb_finding_for_prune(tmp_path, "old", status="superseded")
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        _add_role_preload_entries(role_path, [
            "8. /areas/research/kb/findings/f-2026-05-old.md",
        ])
        config = _load_config(tmp_path)
        candidates = find_prune_candidates(tmp_path, config)
        plan = plan_prune(candidates, tmp_path)
        assert len(plan.changes) >= 1
        apply_plan(plan, tmp_path)

        role_text_after = role_path.read_text()
        assert "f-2026-05-old.md" not in role_text_after

    def test_capability_managed_entries_skipped(self, tmp_path: Path) -> None:
        """An entry that is in a # capability: block should be skipped with a warning."""
        _write_basic_repo(tmp_path)
        _write_kb_finding_for_prune(tmp_path, "managed", status="superseded")
        role_path = tmp_path / "areas/research/roles/researcher/role.md"
        text = role_path.read_text()
        new_text = text.replace(
            "## Preload context (frontmatter only)",
            "# capability: por\n- /areas/research/kb/findings/f-2026-05-managed.md\n# end capability: por\n\n## Preload context (frontmatter only)",
            1,
        )
        role_path.write_text(new_text)

        config = _load_config(tmp_path)
        candidates = find_prune_candidates(tmp_path, config)
        plan = plan_prune(candidates, tmp_path)
        # Plan should warn about the capability-managed entry
        assert any("capability" in w for w in plan.warnings)
        # Apply should NOT remove the entry
        apply_plan(plan, tmp_path)
        assert "f-2026-05-managed.md" in role_path.read_text()


class TestFormatPruneCandidates:
    def test_empty(self) -> None:
        assert format_prune_candidates([]) == "No prune candidates."

    def test_groups_by_role(self) -> None:
        candidates = [
            PruneCandidate(
                role_file="areas/research/roles/researcher/role.md",
                role_name="researcher",
                preload_path="/areas/research/kb/findings/f-x.md",
                tier="full",
                reason="target page has status 'dropped'",
                detail={"page_status": "dropped"},
            ),
        ]
        out = format_prune_candidates(candidates)
        assert "researcher" in out
        assert "/areas/research/kb/findings/f-x.md" in out
        assert "dropped" in out
