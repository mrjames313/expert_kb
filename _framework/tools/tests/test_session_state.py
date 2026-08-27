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

    def test_none_when_no_authoritative_source(self, tmp_path: Path) -> None:
        # No recorded path and no cwd/session_id → None (never guesses from disk).
        assert ss.context_tokens(tmp_path) is None
        assert ss.context_tokens(tmp_path, cwd="/some/where") is None  # missing session_id

    def test_reconstructs_from_cwd_and_session_id(self, tmp_path: Path, monkeypatch) -> None:
        import re
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        cwd = "/launch/dir"
        sid = "sess-abc"
        munged = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
        proj = home / ".claude" / "projects" / munged
        proj.mkdir(parents=True)
        (proj / f"{sid}.jsonl").write_text(json.dumps({
            "type": "assistant",
            "message": {"usage": {"input_tokens": 4,
                                  "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": 200}},
        }) + "\n")
        assert ss.context_tokens(tmp_path, cwd=cwd, session_id=sid) == 204


class TestTranscriptForSession:
    def test_exact_path_keyed_on_cwd_not_repo(self, tmp_path: Path, monkeypatch) -> None:
        """Regression: keyed on the session cwd (munged) + session id — not the
        repo root, and not an mtime guess among sibling transcripts."""
        import re
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        cwd = "/Users/x/projects"          # session launched in a parent dir
        sid = "the-session"
        proj = home / ".claude" / "projects" / re.sub(r"[^a-zA-Z0-9]", "-", cwd)
        proj.mkdir(parents=True)
        target = proj / f"{sid}.jsonl"
        target.write_text("{}\n")
        # A sibling dir (repo-root-derived) with a newer, foreign transcript.
        other = home / ".claude" / "projects" / "-Users-x-projects-myrepo"
        other.mkdir(parents=True)
        (other / "foreign.jsonl").write_text("{}\n")
        assert ss.transcript_for_session(cwd, sid) == target

    def test_none_without_identity_or_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "h"))
        assert ss.transcript_for_session(None, "s") is None
        assert ss.transcript_for_session("/c", None) is None
        assert ss.transcript_for_session("/c", "missing") is None  # file absent
