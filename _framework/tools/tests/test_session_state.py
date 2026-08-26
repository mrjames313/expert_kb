"""
Tests for _framework/tools/session_state.py
"""

from __future__ import annotations

import json
from pathlib import Path

import session_state as ss


class TestReadWrite:
    def test_read_absent_is_empty(self, tmp_path: Path) -> None:
        assert ss.read(tmp_path) == {}

    def test_read_malformed_is_empty(self, tmp_path: Path) -> None:
        ss.session_path(tmp_path).write_text("not json{")
        assert ss.read(tmp_path) == {}

    def test_write_merges(self, tmp_path: Path) -> None:
        ss.write(tmp_path, role="researcher")
        ss.write(tmp_path, area="areas/research")
        state = ss.read(tmp_path)
        assert state["role"] == "researcher"
        assert state["area"] == "areas/research"

    def test_write_none_removes_key(self, tmp_path: Path) -> None:
        ss.write(tmp_path, last_wrapup_at="2026-08-26")
        ss.write(tmp_path, last_wrapup_at=None)
        assert "last_wrapup_at" not in ss.read(tmp_path)


class TestAdoptAndNewSession:
    def test_adopt_stamps_role_area_time(self, tmp_path: Path) -> None:
        ss.adopt(tmp_path, "researcher", "areas/research")
        state = ss.read(tmp_path)
        assert state["role"] == "researcher"
        assert state["area"] == "areas/research"
        assert state["started_at"]  # timestamp present

    def test_new_session_drops_role_keeps_identity(self, tmp_path: Path) -> None:
        ss.adopt(tmp_path, "researcher", "areas/research")
        ss.new_session(tmp_path, session_id="sess-2", transcript_path="/t/x.jsonl")
        state = ss.read(tmp_path)
        assert "role" not in state and "area" not in state  # reset
        assert state["session_id"] == "sess-2"
        assert state["transcript_path"] == "/t/x.jsonl"

    def test_adopt_overwrites_after_new_session(self, tmp_path: Path) -> None:
        """/start is authoritative even when the hook left only session identity."""
        ss.new_session(tmp_path, session_id="sess-2", transcript_path="/t/x.jsonl")
        ss.adopt(tmp_path, "engineer", "areas/engineering")
        state = ss.read(tmp_path)
        assert state["role"] == "engineer"
        assert state["session_id"] == "sess-2"  # identity preserved (merge)

    def test_reset_deletes(self, tmp_path: Path) -> None:
        ss.adopt(tmp_path, "researcher", "areas/research")
        ss.reset(tmp_path)
        assert not ss.session_path(tmp_path).exists()


def _transcript(tmp_path: Path, usages: list[dict]) -> Path:
    """Write a JSONL transcript; each usage becomes an assistant line, with a
    plain non-usage line interleaved."""
    p = tmp_path / "t.jsonl"
    lines = []
    for u in usages:
        lines.append(json.dumps({"type": "user", "message": {"content": "hi"}}))
        lines.append(json.dumps({"type": "assistant", "message": {"usage": u}}))
    p.write_text("\n".join(lines) + "\n")
    return p


class TestTranscriptTokens:
    def test_sums_last_usage(self, tmp_path: Path) -> None:
        p = _transcript(tmp_path, [
            {"input_tokens": 1, "cache_creation_input_tokens": 2, "cache_read_input_tokens": 3},
            {"input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100},
        ])
        assert ss.transcript_tokens(p) == 115  # last turn: 10 + 5 + 100

    def test_none_when_no_usage(self, tmp_path: Path) -> None:
        p = tmp_path / "t.jsonl"
        p.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        assert ss.transcript_tokens(p) is None

    def test_none_when_missing_file(self, tmp_path: Path) -> None:
        assert ss.transcript_tokens(tmp_path / "nope.jsonl") is None
        assert ss.transcript_tokens(None) is None


class TestContextTokens:
    def test_uses_recorded_transcript(self, tmp_path: Path) -> None:
        p = _transcript(tmp_path, [
            {"input_tokens": 4, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 200},
        ])
        ss.write(tmp_path, transcript_path=str(p))
        assert ss.context_tokens(tmp_path) == 204

    def test_none_when_no_transcript_anywhere(self, tmp_path: Path, monkeypatch) -> None:
        # No recorded path; point HOME at an empty dir so find_current_transcript misses.
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
        assert ss.context_tokens(tmp_path) is None


class TestFindCurrentTranscript:
    def test_picks_newest_in_munged_dir(self, tmp_path: Path, monkeypatch) -> None:
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        repo = tmp_path / "proj"
        repo.mkdir()
        import re
        munged = re.sub(r"[^a-zA-Z0-9]", "-", str(repo.resolve()))
        proj_dir = home / ".claude" / "projects" / munged
        proj_dir.mkdir(parents=True)
        old = proj_dir / "old.jsonl"
        new = proj_dir / "new.jsonl"
        old.write_text("{}\n")
        new.write_text("{}\n")
        import os
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        assert ss.find_current_transcript(repo) == new

    def test_none_when_dir_absent(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "empty"))
        assert ss.find_current_transcript(tmp_path / "proj") is None
