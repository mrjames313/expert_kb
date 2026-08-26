"""
Tests for _framework/tools/framework_check.py — the hard-edge drift checks.
"""

from __future__ import annotations

from pathlib import Path

from common import find_repo_root
from framework import _discover_configurable_lint_rules
from framework_check import (
    check_config_matches_rules,
    check_no_dangling_maintainer_refs,
    check_version_matches_latest_release,
    run_all,
)


def _write_config(tmp_path: Path, keys, *, version: str = "2026-08-25") -> None:
    (tmp_path / "_framework").mkdir(parents=True, exist_ok=True)
    if keys:
        wv = "\n".join(f"    {k}: false" for k in keys)
        body = f"framework_version: {version}\nlint:\n  warnings_visible:\n{wv}\n"
    else:
        body = f"framework_version: {version}\nlint:\n  warnings_visible: {{}}\n"
    (tmp_path / "_framework" / "config.yml").write_text(body)


class TestConfigMatchesRules:
    def test_clean_when_config_lists_exactly_shipped(self, tmp_path: Path) -> None:
        _write_config(tmp_path, sorted(_discover_configurable_lint_rules()))
        assert check_config_matches_rules(tmp_path) == []

    def test_flags_missing_key(self, tmp_path: Path) -> None:
        shipped = sorted(_discover_configurable_lint_rules())
        _write_config(tmp_path, shipped[:-1])  # drop one shipped key
        problems = check_config_matches_rules(tmp_path)
        assert any("missing" in p and shipped[-1] in p for p in problems)

    def test_flags_stale_extra_key(self, tmp_path: Path) -> None:
        _write_config(tmp_path, sorted(_discover_configurable_lint_rules()) + ["rule_99_ghost"])
        problems = check_config_matches_rules(tmp_path)
        assert any("rule_99_ghost" in p and "no such warning" in p for p in problems)


class TestNoDanglingMaintainerRefs:
    def _pulled_doc(self, tmp_path: Path, text: str) -> None:
        d = tmp_path / "_framework" / "schema"
        d.mkdir(parents=True, exist_ok=True)
        (d / "sample.md").write_text(text)

    def test_flags_reference_to_future_work(self, tmp_path: Path) -> None:
        self._pulled_doc(tmp_path, "See `future-work.md` for the backlog.\n")
        problems = check_no_dangling_maintainer_refs(tmp_path)
        assert len(problems) == 1
        assert "future-work.md" in problems[0]

    def test_flags_reference_to_maintaining(self, tmp_path: Path) -> None:
        self._pulled_doc(tmp_path, "per maintaining.md → Releasing a framework change\n")
        problems = check_no_dangling_maintainer_refs(tmp_path)
        assert any("maintaining.md" in p for p in problems)

    def test_clean_when_self_contained(self, tmp_path: Path) -> None:
        self._pulled_doc(tmp_path, "Tracked in the framework repo's backlog.\n")
        assert check_no_dangling_maintainer_refs(tmp_path) == []


class TestVersionMatchesLatestRelease:
    def _upgrading(self, tmp_path: Path, dates) -> None:
        blocks = "\n\n".join(f"**Release {d}**\n\n- something." for d in dates)
        (tmp_path / "UPGRADING.md").write_text(f"# Upgrading\n\n{blocks}\n")

    def test_clean_when_version_is_latest(self, tmp_path: Path) -> None:
        _write_config(tmp_path, [], version="2026-08-25")
        self._upgrading(tmp_path, ["2026-08-14", "2026-08-22", "2026-08-25"])
        assert check_version_matches_latest_release(tmp_path) == []

    def test_flags_version_behind_latest_release(self, tmp_path: Path) -> None:
        _write_config(tmp_path, [], version="2026-08-22")
        self._upgrading(tmp_path, ["2026-08-14", "2026-08-25"])
        problems = check_version_matches_latest_release(tmp_path)
        assert any("!= latest" in p for p in problems)

    def test_flags_non_ascending_releases(self, tmp_path: Path) -> None:
        _write_config(tmp_path, [], version="2026-08-14")
        self._upgrading(tmp_path, ["2026-08-25", "2026-08-14"])
        problems = check_version_matches_latest_release(tmp_path)
        assert any("ascending" in p for p in problems)

    def test_skips_when_no_upgrading(self, tmp_path: Path) -> None:
        _write_config(tmp_path, [], version="2026-08-25")  # no UPGRADING.md (bootstrapped project)
        assert check_version_matches_latest_release(tmp_path) == []


def test_real_repo_is_self_consistent() -> None:
    """Standing regression guard: the framework repo must pass its own hard-edge
    checks. This would have caught the enable-lint config drift, the dangling
    template-only references, and any version/release mismatch."""
    assert run_all(find_repo_root()) == []
