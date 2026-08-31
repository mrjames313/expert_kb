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

    def test_context_bloat_fires_without_role(self, tmp_path: Path) -> None:
        """The restart nudge is session-scoped — it must surface even when no role
        is adopted (regression: it was gated behind role adoption)."""
        make_minimal_repo(tmp_path)
        # Record a transcript with tokens over a low threshold, but no role/area.
        t = tmp_path / "t.jsonl"
        t.write_text(
            '{"type":"assistant","message":{"usage":{"input_tokens":500,'
            '"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n'
        )
        ss.write(tmp_path, transcript_path=str(t))
        config = {"lint": {}, "capabilities": {}, "kb_vitals": {"context_restart_threshold_tokens": 100}}
        vitals = kv.role_vitals(tmp_path, config)
        assert any("context ~" in v.message for v in vitals)
        assert any("no role adopted" in v.message for v in vitals)

    def test_scopes_to_this_session_not_a_concurrent_one(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Role vitals key on $CLAUDE_CODE_SESSION_ID: a second session's adopted
        role in the same repo must not scope this session's checks."""
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        (tmp_path / "areas/research/_journal/pulse.log").write_text("## [x] decision r\nfoo\n")
        ss.adopt(tmp_path, "researcher", "areas/research", session_id="sess-a")
        ss.adopt(tmp_path, "reviewer", "areas/engineering", session_id="sess-b")

        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-a")
        assert any("uncompacted pulse.log" in m
                   for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-b")
        # sess-b is in an area with no pulse.log of its own — nothing to compact.
        assert not any("uncompacted pulse.log" in m
                       for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

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


# --- Exchanges (multi_area) ---

_MULTI = {"lint": {"pulse_line_cap": 80}, "capabilities": {"multi_area": True}, "kb_vitals": {}}


def _exchange(repo: Path, id_: str, **fm: str) -> Path:
    """Write an exchange the way `/exchange` does: `exchanges/<a>--<b>/ex-<date>-<slug>.md`
    with *bare* area names — the contract in exchange-protocol.md."""
    ex = repo / "exchanges" / "engineering--research"
    ex.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    path = ex / f"{id_}.md"
    path.write_text(f"---\nid: {id_}\n{lines}\ncreated: 2026-08-28\n---\n# Question\nText.\n")
    return path


class TestExchangeCounts:
    """Unit-level: the two silent defects were a glob that matched no real file
    and an area compared across two formats."""

    def test_matches_the_real_filename_form(self, tmp_path: Path) -> None:
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="open",
                  from_area="engineering", to_area="research")
        assert kv.exchange_counts(tmp_path, "areas/research").to_answer == 1

    def test_accepts_both_area_forms(self, tmp_path: Path) -> None:
        """Callers pass the repo-relative form (session state, cache writer);
        frontmatter uses the bare form. Both must resolve."""
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="open",
                  from_area="engineering", to_area="research")
        assert kv.exchange_counts(tmp_path, "areas/research").to_answer == 1
        assert kv.exchange_counts(tmp_path, "research").to_answer == 1

    def test_sub_area_normalises_to_the_nested_form(self, tmp_path: Path) -> None:
        _exchange(tmp_path, "ex-2026-08-28-optics", kind="query", status="open",
                  from_area="engineering", to_area="research/optics")
        assert kv.exchange_counts(tmp_path, "areas/research/optics").to_answer == 1

    def test_answered_query_counts_for_the_filer(self, tmp_path: Path) -> None:
        _exchange(tmp_path, "ex-2026-08-28-drift", kind="query", status="answered",
                  from_area="research", to_area="engineering")
        counts = kv.exchange_counts(tmp_path, "areas/research")
        assert (counts.to_answer, counts.to_close) == (0, 1)

    def test_kind_defaults_to_query(self, tmp_path: Path) -> None:
        """`kind` is optional in the schema and defaults to query."""
        _exchange(tmp_path, "ex-2026-08-28-legacy", status="open",
                  from_area="engineering", to_area="research")
        assert kv.exchange_counts(tmp_path, "areas/research").to_answer == 1

    def test_brief_is_counted_by_open_for_not_to_area(self, tmp_path: Path) -> None:
        _exchange(tmp_path, "ex-2026-08-28-model", kind="brief", status="open",
                  from_area="engineering", to_area="research",
                  to_roles="[researcher, reviewer]", open_for="[researcher]")
        counts = kv.exchange_counts(tmp_path, "areas/research")
        assert counts.briefs_by_role == {"researcher": 1}
        assert counts.to_answer == 0  # never folded into the query total

    def test_follow_up_query_is_owed_by_the_responder(self, tmp_path: Path) -> None:
        """`exchange-protocol.md`: an unsatisfied asker "fills the Follow-up
        section, sets status `follow_up`, and the responder cycle repeats" — so
        the ball is back with the responder, exactly as when the query was
        filed. Counting only `open` stranded it: no vital, no /start surfacing,
        and (once Rule 14 lands) no staleness ageing either."""
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="follow_up",
                  from_area="engineering", to_area="research")
        counts = kv.exchange_counts(tmp_path, "areas/research")
        assert (counts.to_answer, counts.to_close) == (1, 0)

    def test_follow_up_is_not_owed_by_the_asker(self, tmp_path: Path) -> None:
        """The asker set the status; nothing is owed back to them until the
        responder answers again."""
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="follow_up",
                  from_area="engineering", to_area="research")
        counts = kv.exchange_counts(tmp_path, "areas/engineering")
        assert (counts.to_answer, counts.to_close) == (0, 0)

    def test_follow_up_routes_to_respond_exchange(self, tmp_path: Path) -> None:
        """A count computed correctly and sent to the wrong command is the
        failure mode a counts-only assertion misses."""
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="follow_up",
                  from_area="engineering", to_area="research")
        vitals = kv._exchange_vitals(tmp_path, "areas/research", "researcher")
        assert [v.command for v in vitals] == ["/respond-exchange"]

    def test_closed_query_is_owed_by_nobody(self, tmp_path: Path) -> None:
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="closed",
                  from_area="engineering", to_area="research")
        for area in ("areas/research", "areas/engineering"):
            counts = kv.exchange_counts(tmp_path, area)
            assert (counts.to_answer, counts.to_close) == (0, 0)

    def test_no_exchanges_dir(self, tmp_path: Path) -> None:
        counts = kv.exchange_counts(tmp_path, "areas/research")
        assert (counts.to_answer, counts.to_close, counts.briefs_by_role) == (0, 0, {})


class TestExchangeVitals:
    """End-to-end through role_vitals: the right command for each kind."""

    def test_open_query_routes_to_respond(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="open",
                  from_area="engineering", to_area="research")
        vitals = [v for v in kv.role_vitals(tmp_path, _MULTI) if "query" in v.message]
        assert len(vitals) == 1
        assert vitals[0].command == "/respond-exchange"

    def test_answered_query_routes_to_close(self, tmp_path: Path) -> None:
        """The case with no second line of defence: `/start`'s manual scan
        surfaces open-to-you exchanges, but nothing else surfaces this one."""
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _exchange(tmp_path, "ex-2026-08-28-drift", kind="query", status="answered",
                  from_area="research", to_area="engineering")
        vitals = [v for v in kv.role_vitals(tmp_path, _MULTI) if "to close" in v.message]
        assert len(vitals) == 1
        assert vitals[0].command == "/close-exchange"

    def test_brief_for_your_role_routes_to_close_not_respond(self, tmp_path: Path) -> None:
        """A brief has no responder — pointing it at /respond-exchange was defect 3."""
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _exchange(tmp_path, "ex-2026-08-28-model", kind="brief", status="open",
                  from_area="engineering", to_area="research",
                  to_roles="[researcher]", open_for="[researcher]")
        vitals = [v for v in kv.role_vitals(tmp_path, _MULTI) if "brief" in v.message]
        assert len(vitals) == 1
        assert vitals[0].command == "/close-exchange"
        assert not any("/respond-exchange" == v.command for v in kv.role_vitals(tmp_path, _MULTI))

    def test_brief_not_addressed_to_your_role_is_silent(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _exchange(tmp_path, "ex-2026-08-28-model", kind="brief", status="open",
                  from_area="engineering", to_area="research",
                  to_roles="[reviewer]", open_for="[reviewer]")
        assert not any("brief" in m for m in _msgs(kv.role_vitals(tmp_path, _MULTI), "role"))

    def test_silent_when_multi_area_is_off(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _exchange(tmp_path, "ex-2026-08-28-thermal", kind="query", status="open",
                  from_area="engineering", to_area="research")
        assert not any("query" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))


# --- Hooks-inactive detector ---

class TestHooksInactive:
    """`transcript_path` is written only by the lifecycle hooks, so its absence
    in a repo that registers them means they never fired — the silent failure
    that happens when the framework is installed into a running process."""

    def _settings(self, repo: Path, hooks: bool = True) -> None:
        d = repo / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        body = '{"hooks": {"SessionStart": []}}' if hooks else '{"model": "opus"}'
        (d / "settings.json").write_text(body)

    def test_fires_when_hooks_registered_but_never_ran(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        self._settings(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")   # no transcript_path
        assert any("didn't fire" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_silent_when_hooks_ran(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        self._settings(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        ss.write(tmp_path, transcript_path="/tmp/t.jsonl")   # only a hook sets this
        assert not any("didn't fire" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_silent_when_no_hooks_configured(self, tmp_path: Path) -> None:
        """Hooks are optional. A project that never registered them isn't broken."""
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        self._settings(tmp_path, hooks=False)
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert not any("didn't fire" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))

    def test_silent_when_no_settings_file(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _setup_area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert not any("didn't fire" in m for m in _msgs(kv.role_vitals(tmp_path, _CONFIG), "role"))
