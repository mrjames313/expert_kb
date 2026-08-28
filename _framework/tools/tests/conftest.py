"""
Shared pytest fixtures and helpers for tool tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Make _framework/tools importable
TOOLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture(autouse=True)
def _no_ambient_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session state is keyed on `$CLAUDE_CODE_SESSION_ID`, which is set whenever
    the suite runs inside Claude Code. Drop it so tests key on the `default`
    fallback (or an id they set themselves) rather than on the runner's session.
    """
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create an empty git repo in tmp_path. Returns the repo root."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    return tmp_path


def make_commit(
    repo: Path,
    filename: str,
    content: str = "x",
    commit_date: date | str | None = None,
    message: str | None = None,
) -> None:
    """Create or update a file and commit it. Optionally backdate the commit."""
    file_path = repo / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    subprocess.run(["git", "add", filename], cwd=repo, check=True)

    env = os.environ.copy()
    if commit_date:
        date_str = commit_date if isinstance(commit_date, str) else commit_date.isoformat()
        # Use noon for the time so timezone offsets don't push dates
        iso_dt = f"{date_str}T12:00:00"
        env["GIT_AUTHOR_DATE"] = iso_dt
        env["GIT_COMMITTER_DATE"] = iso_dt

    msg = message or f"commit {filename}"
    subprocess.run(
        ["git", "commit", "-q", "-m", msg],
        cwd=repo,
        env=env,
        check=True,
    )


def days_ago(n: int) -> date:
    """Return the date n days before today."""
    return date.today() - timedelta(days=n)
