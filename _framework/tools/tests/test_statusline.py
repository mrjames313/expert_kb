"""
Tests for _framework/tools/statusline.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import session_state as ss
import vitals_cache as vc
from statusline import build_line
from lint_helpers import make_minimal_repo

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _plain(line: str) -> str:
    """The rendered line with color stripped — most assertions don't care."""
    return _ANSI.sub("", line)


def _transcript(tmp_path: Path, total_tokens: int) -> str:
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({
        "type": "assistant",
        "message": {"usage": {"input_tokens": total_tokens,
                              "cache_creation_input_tokens": 0,
                              "cache_read_input_tokens": 0}},
    }) + "\n")
    return str(p)


def _area(tmp_path: Path, area: str = "areas/research") -> Path:
    d = tmp_path / area
    (d / "_journal").mkdir(parents=True, exist_ok=True)
    (d / "_journal" / "pulse.log").write_text("")
    (d / "pulse.md").write_text("# pulse\n")
    return d


class TestIndicators:
    def test_clear_repo_shows_both_green(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _area(tmp_path)
        assert "H✓ R✓" in _plain(build_line(tmp_path, {}))

    def test_no_role_shows_r_as_not_applicable(self, tmp_path: Path) -> None:
        """`R–` is not `R✓`: with no role adopted there's nothing to scope the
        checks to, which is different from having checked and found nothing."""
        make_minimal_repo(tmp_path)
        line = _plain(build_line(tmp_path, {}))
        assert "(no role)" in line and "R–" in line

    def test_human_count_sums_live_and_cached(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text(
            "# Inbox\n\n## Needs decision\n\n- a\n- b\n\n"
            "## Awaiting your ack\n\n- c\n\n## Heads up\n\n- not counted\n"
        )
        prop = tmp_path / "commons" / "_proposed" / "p1"
        prop.mkdir(parents=True)
        (prop / "page.md").write_text("---\nid: f-x\n---\n")
        vc.write(tmp_path, {"commons_awaiting_review": 2})
        # 2 decisions + 1 ack + 1 proposal + 2 commons pages awaiting review
        assert "H6" in _plain(build_line(tmp_path, {}))

    def test_heads_up_section_is_not_counted(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Heads up\n\n- a\n- b\n")
        assert "H✓" in _plain(build_line(tmp_path, {}))

    def test_role_count_sums_live_and_cached(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area = _area(tmp_path)
        (area / "_journal" / "pulse.log").write_text("## [x] decision r\nfoo\n")
        (area / "pulse.md").write_text("\n".join(f"line {i}" for i in range(90)))
        spec = area / "specs" / "s1"
        spec.mkdir(parents=True)
        (spec / "tasks.md").write_text("# Tasks\n\n### T1\n_Status:_ done\n")
        vc.write(tmp_path, {"areas": {"areas/research": {
            "exchanges_to_answer": 1, "exchanges_to_close": 1}}})
        ss.adopt(tmp_path, "researcher", "areas/research")
        # pulse.log + pulse.md over cap + spec complete w/o outcome + 2 exchanges
        assert "R5" in _plain(build_line(tmp_path, {}))

    def test_briefs_count_only_for_the_adopted_role(self, tmp_path: Path) -> None:
        """R is the *adopted role's* hygiene, and a brief is owed by the roles in
        its `open_for` — so a brief for another role must not light this one up."""
        make_minimal_repo(tmp_path)
        _area(tmp_path)
        vc.write(tmp_path, {"areas": {"areas/research": {"roles": {
            "researcher": {"briefs_open": 2},
            "reviewer": {"briefs_open": 5},
        }}}})
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert "R2" in _plain(build_line(tmp_path, {}))

    def test_stale_preload_compares_cache_against_this_session(self, tmp_path: Path) -> None:
        """The cache holds the preload's newest `updated`; whether that is stale
        depends on when *this* session adopted, which is per-session state."""
        make_minimal_repo(tmp_path)
        _area(tmp_path)
        vc.write(tmp_path, {"areas": {"areas/research": {
            "roles": {"researcher": {"preload_newest_update": "2026-08-20"}}}}})

        ss.write(tmp_path, role="researcher", area="areas/research",
                 started_at="2026-08-01T09:00:00")   # adopted before the update
        assert "R1" in _plain(build_line(tmp_path, {}))

        ss.write(tmp_path, started_at="2026-08-26T09:00:00")  # adopted after it
        assert "R✓" in _plain(build_line(tmp_path, {}))

    def test_missing_cache_degrades_to_live_only(self, tmp_path: Path) -> None:
        """No snapshot yet (fresh clone, hooks never fired) must not crash or
        invent counts — the live vitals still show."""
        make_minimal_repo(tmp_path)
        _area(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Needs decision\n\n- a\n")
        assert not vc.path(tmp_path).exists()
        assert "H1 R✓" in _plain(build_line(tmp_path, {}))

    def test_malformed_cache_degrades(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        vc.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        vc.path(tmp_path).write_text("{not json")
        assert "H✓" in _plain(build_line(tmp_path, {}))


class TestSeverityColor:
    def test_decision_pending_reads_red(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Needs decision\n\n- a\n")
        assert "\033[31mH1" in build_line(tmp_path, {})

    def test_ack_only_reads_yellow(self, tmp_path: Path) -> None:
        """An ack is hygiene; a decision blocks work. Different colors."""
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Awaiting your ack\n\n- a\n")
        assert "\033[33mH1" in build_line(tmp_path, {})

    def test_blocked_task_reads_red(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area = _area(tmp_path)
        spec = area / "specs" / "s1"
        spec.mkdir(parents=True)
        (spec / "tasks.md").write_text("# Tasks\n\n### T1\n_Status:_ blocked\n")
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert "\033[31mR1" in build_line(tmp_path, {})

    def test_clear_reads_green(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        assert "\033[32mH✓" in build_line(tmp_path, {})

    def test_config_can_disable_color(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        cfg = tmp_path / "_framework" / "config.yml"
        cfg.write_text(cfg.read_text() + "statusline:\n  color: false\n")
        assert "\033[" not in build_line(tmp_path, {})

    def test_no_color_env_disables_color(self, tmp_path: Path, monkeypatch) -> None:
        make_minimal_repo(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        assert "\033[" not in build_line(tmp_path, {})

    def test_color_key_is_scoped_to_its_section(self, tmp_path: Path) -> None:
        """A `color:` key belonging to some other section must not turn the
        status line monochrome."""
        make_minimal_repo(tmp_path)
        cfg = tmp_path / "_framework" / "config.yml"
        cfg.write_text("someothertool:\n  color: false\n" + cfg.read_text())
        assert "\033[" in build_line(tmp_path, {})


class TestHint:
    def test_hint_appears_when_something_is_pending(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text("# Inbox\n\n## Needs decision\n\n- a\n")
        assert _plain(build_line(tmp_path, {})).endswith("run /kb-vitals")

    def test_no_hint_when_clear(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        _area(tmp_path)
        assert "/kb-vitals" not in build_line(tmp_path, {})


class TestSessionScope:
    def test_each_session_sees_its_own_role(self, tmp_path: Path) -> None:
        """Two sessions in one repo: each status line reads its own state file,
        keyed on the payload's session_id."""
        make_minimal_repo(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research", session_id="sess-a")
        ss.adopt(tmp_path, "reviewer", "areas/engineering", session_id="sess-b")
        assert "researcher@research" in build_line(tmp_path, {"session_id": "sess-a"})
        assert "reviewer@engineering" in build_line(tmp_path, {"session_id": "sess-b"})


class TestContext:
    def test_context_over_threshold_marks_bang(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)  # default threshold 400000
        line = build_line(tmp_path, {"transcript_path": _transcript(tmp_path, 500_000)})
        assert "ctx 500k!" in _plain(line)

    def test_context_under_threshold_no_bang(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        line = _plain(build_line(tmp_path, {"transcript_path": _transcript(tmp_path, 120_000)}))
        assert "ctx 120k" in line and "!" not in line

    def test_no_transcript_omits_ctx(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        line = _plain(build_line(tmp_path, {}))  # no transcript anywhere
        # No ctx field → project, who, indicators (nothing pending → no hint).
        assert len(line.split(" · ")) == 3


class TestTailReader:
    def test_tail_reads_last_usage_on_large_file(self, tmp_path: Path) -> None:
        p = tmp_path / "big.jsonl"
        filler = json.dumps({"type": "user", "message": {"content": "x" * 1000}})
        last = json.dumps({"type": "assistant", "message": {"usage": {
            "input_tokens": 7, "cache_creation_input_tokens": 3, "cache_read_input_tokens": 90}}})
        p.write_text("\n".join([filler] * 500 + [last]) + "\n")
        assert ss.transcript_tokens_tail(p, tail_bytes=4096) == 100

    def test_tail_none_when_no_usage_in_tail(self, tmp_path: Path) -> None:
        p = tmp_path / "n.jsonl"
        p.write_text("\n".join(json.dumps({"type": "user"}) for _ in range(50)) + "\n")
        assert ss.transcript_tokens_tail(p) is None
