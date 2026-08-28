"""
Tests for _framework/tools/statusline.py
"""

from __future__ import annotations

import json
from pathlib import Path

import session_state as ss
from statusline import build_line
from lint_helpers import make_minimal_repo


def _transcript(tmp_path: Path, total_tokens: int) -> str:
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({
        "type": "assistant",
        "message": {"usage": {"input_tokens": total_tokens,
                              "cache_creation_input_tokens": 0,
                              "cache_read_input_tokens": 0}},
    }) + "\n")
    return str(p)


class TestBuildLine:
    def test_no_role(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        line = build_line(tmp_path, {})
        assert "(no role)" in line
        assert " · ✓" in line  # nothing pending

    def test_role_and_area(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research")
        assert "researcher@research" in build_line(tmp_path, {})

    def test_each_session_sees_its_own_role(self, tmp_path: Path) -> None:
        """Two sessions in one repo: each status line reads its own state file,
        keyed on the payload's session_id."""
        make_minimal_repo(tmp_path)
        ss.adopt(tmp_path, "researcher", "areas/research", session_id="sess-a")
        ss.adopt(tmp_path, "reviewer", "areas/engineering", session_id="sess-b")
        assert "researcher@research" in build_line(tmp_path, {"session_id": "sess-a"})
        assert "reviewer@engineering" in build_line(tmp_path, {"session_id": "sess-b"})

    def test_pending_human_count(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        (tmp_path / "INBOX.md").write_text(
            "# Inbox\n\n## Needs decision\n\n- a\n- b\n\n"
            "## Awaiting your ack\n\n- c\n\n## Heads up\n\n_None._\n"
        )
        assert "⚠3" in build_line(tmp_path, {})

    def test_context_over_threshold_marks_bang(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)  # default threshold 400000
        line = build_line(tmp_path, {"transcript_path": _transcript(tmp_path, 500_000)})
        assert "ctx 500k!" in line

    def test_context_under_threshold_no_bang(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        line = build_line(tmp_path, {"transcript_path": _transcript(tmp_path, 120_000)})
        assert "ctx 120k" in line and "!" not in line

    def test_no_transcript_omits_ctx(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        line = build_line(tmp_path, {})  # no transcript anywhere
        # No ctx field → exactly 3 " · "-joined parts (project, who, indicator).
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
