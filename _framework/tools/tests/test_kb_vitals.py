"""
Tests for _framework/tools/kb_vitals.py
"""

from __future__ import annotations

from pathlib import Path

import session_state as ss
import kb_vitals as kv
from lint_helpers import make_minimal_repo

_CONFIG = {"lint": {"pulse_line_cap": 80}, "capabilities": {}, "kb_vitals": {}}


def _msgs(vitals, scope):
    return [v.message for v in vitals if v.scope == scope]


def _setup_area(repo: Path, area: str = "areas/research", role: str = "researcher") -> Path:
    d = repo / area
    (d / "_journal").mkdir(parents=True, exist_ok=True)
    (d / "roles" / role).mkdir(parents=True, exist_ok=True)
    (d / "specs").mkdir(parents=True, exist_ok=True)
    (d / "pulse.md").write_text("# pulse\n")
    (d / "_journal" / "pulse.log").write_text("")
    return d


# --- Human vitals ---

class TestHumanVitals:
    def test_needs_decision(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text(
            "# Inbox\n\n## Needs decision\n\n- Two findings conflict\n\n"
            "## Awaiting your ack\n\n_None._\n\n## Heads up\n\n_None._\n"
        )
        assert any("need your decision" in m for m in _msgs(kv.human_vitals(tmp_path), "human"))

    def test_awaiting_ack(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        cdir = tmp_path / "commons" / "kb" / "findings"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "f-commons-x.md").write_text(
            "---\nid: f-commons-x\ntype: finding\narea: commons\nhuman_reviewed: false\n"
            "summary: x\n---\n\nBody.\n"
        )
        assert any("awaiting your review" in m for m in _msgs(kv.human_vitals(tmp_path), "human"))

    def test_proposal_ready(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        prop = tmp_path / "commons" / "_proposed" / "2026-05-x"
        prop.mkdir(parents=True)
        (prop / "page.md").write_text("---\nid: f-2026-05-x\n---\nBody.\n")
        assert any("ready to promote" in m for m in _msgs(kv.human_vitals(tmp_path), "human"))

    def test_clean_when_nothing_pending(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Needs decision\n\n_None._\n")
        assert kv.human_vitals(tmp_path) == []


# --- Role vitals ---

class TestRoleVitals:
    def test_no_role_adopted(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        vitals = kv.role_vitals(tmp_path, _CONFIG)
        assert len(vitals) == 1 and "no role adopted" in vitals[0].message

    def test_wrapup_due(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        (tmp_path / "areas/research/_journal/pulse.log").write_text("## [x] decision r\nfoo\n")
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert any("uncompacted pulse.log" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_pulse_over_cap(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        (tmp_path / "areas/research/pulse.md").write_text("\n".join(f"line {i}" for i in range(90)))
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert any("over cap" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_spec_complete_needs_outcome(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        spec = tmp_path / "areas/research/specs/myspec"
        spec.mkdir(parents=True)
        (spec / "tasks.md").write_text(
            "# Tasks\n\n### T1\n_Status:_ done\n\n### T2\n_Status:_ superseded\n"
        )
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert any("complete — no outcome" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_blocked_task(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        spec = tmp_path / "areas/research/specs/myspec"
        spec.mkdir(parents=True)
        (spec / "tasks.md").write_text("# Tasks\n\n### T1\n_Status:_ blocked\n\n### T2\n_Status:_ planned\n")
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert any("blocked task" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_stale_preload(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        # A preloaded kb page updated well after adoption.
        page = tmp_path / "areas/research/kb/findings"
        page.mkdir(parents=True, exist_ok=True)
        (page / "f-x.md").write_text("---\nid: f-x\nupdated: 2026-05-08\n---\nBody.\n")
        (tmp_path / "areas/research/roles/researcher/role.md").write_text(
            "# researcher\n\n## Preload context (full)\n\n"
            "1. /areas/research/kb/findings/f-x.md\n"
        )
        ss.write(tmp_path, role="researcher", area="areas/research", started_at="2020-01-01T00:00:00")
        assert any("stale" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_fresh_preload_not_flagged(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        page = tmp_path / "areas/research/kb/findings"
        page.mkdir(parents=True, exist_ok=True)
        (page / "f-x.md").write_text("---\nid: f-x\nupdated: 2026-05-08\n---\nBody.\n")
        (tmp_path / "areas/research/roles/researcher/role.md").write_text(
            "# researcher\n\n## Preload context (full)\n\n1. /areas/research/kb/findings/f-x.md\n"
        )
        # Adopted AFTER the page's update → not stale.
        ss.write(tmp_path, role="researcher", area="areas/research", started_at="2026-06-01T00:00:00")
        assert not any("stale" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))
