"""
Tests for _framework/tools/framework_check.py — the hard-edge drift checks.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from common import find_repo_root
from framework import _discover_configurable_lint_rules
from framework_check import (
    _MAINTAINER_ONLY,
    check_config_matches_rules,
    check_framework_remote_is_push_disabled,
    check_maintainer_only_enumerations_agree,
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

    def test_flags_a_future_dated_release(self, tmp_path: Path) -> None:
        """A future stamp mis-gates the next real release: a project upgrading
        today records tomorrow's date, so Step 5 ("apply those whose release is
        newer than your version") silently skips tomorrow's actual release.
        Caught in practice on 2026-08-31, when a same-day change was stamped
        2026-09-01 instead of appending to that day's block."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        _write_config(tmp_path, [], version=tomorrow)
        self._upgrading(tmp_path, ["2026-08-14", tomorrow])
        problems = check_version_matches_latest_release(tmp_path)
        assert any("in the future" in p for p in problems)

    def test_todays_release_is_fine(self, tmp_path: Path) -> None:
        today = date.today().isoformat()
        _write_config(tmp_path, [], version=today)
        self._upgrading(tmp_path, ["2026-08-14", today])
        assert check_version_matches_latest_release(tmp_path) == []

    def test_skips_when_no_upgrading(self, tmp_path: Path) -> None:
        _write_config(tmp_path, [], version="2026-08-25")  # no UPGRADING.md (bootstrapped project)
        assert check_version_matches_latest_release(tmp_path) == []


class TestMaintainerOnlyEnumerationsAgree:
    def test_flags_an_omitted_file(self, tmp_path: Path) -> None:
        """The failure this prevents: a new maintainer-only file is added to
        _MAINTAINER_ONLY but not to the bootstrap `rm`, so it ships into every
        bootstrapped project. Caught on this check's first run, which found a
        third UPGRADING.md site the author had missed."""
        (tmp_path / "SETUP.md").write_text(
            "rm SETUP.md _framework/future-work.md _framework/maintaining.md\n")
        problems = check_maintainer_only_enumerations_agree(tmp_path)
        assert any("omits" in p for p in problems)

    def test_clean_when_all_listed(self, tmp_path: Path) -> None:
        names = " ".join(f"_framework/{n}" for n in _MAINTAINER_ONLY)
        (tmp_path / "SETUP.md").write_text(f"rm SETUP.md {names}\n")
        assert check_maintainer_only_enumerations_agree(tmp_path) == []

    def test_bare_filename_in_prose_is_not_an_enumeration(self, tmp_path: Path) -> None:
        """A release note recalling an old fix names files bare; only a real
        enumeration spells out `_framework/`-prefixed paths. Without this
        distinction the check fires on its own changelog."""
        (tmp_path / "UPGRADING.md").write_text(
            "- Pulled docs referenced `future-work.md`/`maintaining.md` by local path.\n")
        assert check_maintainer_only_enumerations_agree(tmp_path) == []

    def test_skips_when_files_absent(self, tmp_path: Path) -> None:
        assert check_maintainer_only_enumerations_agree(tmp_path) == []


class TestFrameworkRemoteIsPushDisabled:
    """The failure this prevents: a doc tells a project to add the `framework`
    remote, nothing disables its push URL, and one `git push framework main`
    publishes that project's whole knowledge base into the shared template repo.
    Fixtures copy the runbook's own command block (UPGRADING.md Step 0), which is
    the contract these docs are accountable to."""

    def test_flags_an_add_without_the_guard(self, tmp_path: Path) -> None:
        (tmp_path / "UPGRADING.md").write_text(
            "```bash\n"
            "git remote add framework https://github.com/mrjames313/expert_kb.git\n"
            "git fetch framework\n"
            "```\n"
        )
        problems = check_framework_remote_is_push_disabled(tmp_path)
        assert len(problems) == 1
        assert "fetch-only" in problems[0]

    def test_clean_when_the_guard_follows(self, tmp_path: Path) -> None:
        (tmp_path / "UPGRADING.md").write_text(
            "```bash\n"
            "git remote add framework https://github.com/mrjames313/expert_kb.git\n"
            "git remote set-url --push framework DISABLED\n"
            "git fetch framework\n"
            "```\n"
        )
        assert check_framework_remote_is_push_disabled(tmp_path) == []

    def test_guard_in_a_different_block_does_not_count(self, tmp_path: Path) -> None:
        """It must be in the *same* command block. An agent runs the block it is
        given; a guard in some later block is one it may never reach."""
        (tmp_path / "UPGRADING.md").write_text(
            "```bash\n"
            "git remote add framework https://github.com/mrjames313/expert_kb.git\n"
            "```\n"
            "Some prose in between.\n"
            "```bash\n"
            "git remote set-url --push framework DISABLED\n"
            "```\n"
        )
        assert check_framework_remote_is_push_disabled(tmp_path) != []

    def test_prose_mention_is_not_a_command(self, tmp_path: Path) -> None:
        """Caught on this check's first run: the release note announcing the fix
        names `git remote add framework` in prose, and an unfenced match flagged
        the changelog describing the very guard it documents."""
        (tmp_path / "UPGRADING.md").write_text(
            "- Step 0 has told every project to `git remote add framework <url>` "
            "since the upgrade path shipped; it is now push-disabled.\n"
        )
        assert check_framework_remote_is_push_disabled(tmp_path) == []

    def test_skips_when_files_absent(self, tmp_path: Path) -> None:
        """SETUP.md and UPGRADING.md are removed at bootstrap; the check ships
        downstream and must stay quiet there."""
        assert check_framework_remote_is_push_disabled(tmp_path) == []


def test_real_repo_is_self_consistent() -> None:
    """Standing regression guard: the framework repo must pass its own hard-edge
    checks. This would have caught the enable-lint config drift, the dangling
    template-only references, and any version/release mismatch."""
    assert run_all(find_repo_root()) == []
