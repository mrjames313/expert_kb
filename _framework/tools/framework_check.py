"""
Framework self-consistency checks — the mechanically-verifiable "hard edges" of
the doc-dependency graph (see `_framework/future-work.md`). Each check compares a
*derived* value against its *source*, so drift between them fails loudly instead
of accumulating silently — the dominant bug class this framework kept hitting
(enable-lint config drift, dangling references, version/migration mismatch).

Run in the framework repo before pushing, or in CI. Degrades gracefully in a
bootstrapped project: a check whose inputs are absent (e.g. `UPGRADING.md`, which
bootstrap deletes) is skipped, not failed.

Checks:
  1. config `warnings_visible` keys == the shipped warning-rule `CONFIG_KEY`s.
  2. no pulled doc references a maintainer-only file by name — those are
     deleted at bootstrap, so a reference dangles in every live project.
  4. the prose that enumerates the maintainer-only set (SETUP.md's bootstrap
     `rm`, UPGRADING.md's cleanup step) lists exactly `_MAINTAINER_ONLY` — an
     enumerated list in three places is the drift shape this file exists for.
  3. `framework_version` == the latest `**Release <date>**` in `UPGRADING.md`,
     the release dates are in ascending order, and the latest is not in the
     future (a future stamp mis-gates the next real release).
  5. every place that adds the `framework` remote also disables its push URL —
     the remote is fetch-only, and a push to it publishes a project's knowledge
     base into the shared template repo.

Public API:
    run_all(repo_root) -> list[str]      # each string is one problem; [] == clean
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import find_repo_root, load_config  # noqa: E402
from framework import _discover_configurable_lint_rules  # noqa: E402


# Maintainer-only files: deleted at bootstrap, never pulled — a pulled doc must
# not reference them by name (see maintaining.md "Don't reference template-only
# files from pulled docs").
_MAINTAINER_ONLY = (
    "future-work.md",
    "future-work-done.md",
    "maintaining.md",
    "clause-audit.md",
)

# Docs pulled into a live project on upgrade (UPGRADING.md Step 3–4). Kept in sync
# with that step; a reference to a maintainer-only file from any of these dangles.
_PULLED_DOC_GLOBS = (
    "CLAUDE.md",
    "_framework/spec.md",
    "_framework/adoption-guide.md",
    "_framework/schema/*.md",
    "_framework/schema/**/*.md",
    ".claude/skills/**/*.md",
)


def check_config_matches_rules(repo_root: Path) -> list[str]:
    """config `warnings_visible` keys must equal the shipped warning modules' keys."""
    try:
        config = load_config(repo_root)
    except (RuntimeError, OSError):
        return []  # no config → nothing to check (not a framework/project root)

    shipped = _discover_configurable_lint_rules()
    if not shipped:
        return []  # no rule modules found (e.g. partial tree) → skip

    declared = set(
        (config.get("lint", {}).get("warnings_visible", {}) or {}).keys()
    )
    problems: list[str] = []
    for missing in sorted(shipped - declared):
        problems.append(
            f"config.yml warnings_visible is missing `{missing}` — a warning rule "
            f"ships but its visibility key isn't declared."
        )
    for extra in sorted(declared - shipped):
        problems.append(
            f"config.yml warnings_visible declares `{extra}` but no such warning "
            f"rule ships (stale key — remove it or ship the rule)."
        )
    return problems


def check_no_dangling_maintainer_refs(repo_root: Path) -> list[str]:
    """No pulled doc may reference a maintainer-only file by name."""
    problems: list[str] = []
    seen: set[Path] = set()
    for pattern in _PULLED_DOC_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            rel = path.relative_to(repo_root)
            for n, line in enumerate(lines, 1):
                for target in _MAINTAINER_ONLY:
                    if target in line:
                        problems.append(
                            f"{rel}:{n} references maintainer-only `{target}` "
                            f"(deleted at bootstrap; dangles in live projects) — "
                            f"make the statement self-contained."
                        )
    return problems


_RELEASE_RE = re.compile(r"^\*\*Release (\d{4}-\d{2}-\d{2})\*\*", re.MULTILINE)


def check_version_matches_latest_release(repo_root: Path) -> list[str]:
    """`framework_version` must equal the newest UPGRADING.md release; releases ascending."""
    upgrading = repo_root / "UPGRADING.md"
    if not upgrading.is_file():
        return []  # bootstrap removes UPGRADING.md — nothing to check downstream

    try:
        config = load_config(repo_root)
    except (RuntimeError, OSError):
        return []
    version = str(config.get("framework_version", "")).strip()
    if not version:
        return []

    try:
        releases = _RELEASE_RE.findall(upgrading.read_text(encoding="utf-8"))
    except OSError:
        return []
    if not releases:
        return []

    problems: list[str] = []
    if releases != sorted(releases):
        problems.append(
            f"UPGRADING.md release dates are not in ascending order: {releases}"
        )
    latest = max(releases)
    if version != latest:
        problems.append(
            f"framework_version ({version}) != latest UPGRADING.md release ({latest}) "
            f"— bump the version or add the release block so they match."
        )
    # A future-dated release mis-gates every migration after it: a project that
    # upgrades today records tomorrow's date, so Step 5 ("apply those whose
    # release is newer than your version") silently skips tomorrow's real
    # release. Versioning is date-based and per-release, so same-day pushes
    # append to one block rather than inventing the next day's.
    today = date.today().isoformat()
    if latest > today:
        problems.append(
            f"latest UPGRADING.md release ({latest}) is in the future (today is {today}) "
            f"— releases are stamped with today's date; append to today's block instead."
        )
    return problems


def check_maintainer_only_enumerations_agree(repo_root: Path) -> list[str]:
    """The maintainer-only set is enumerated in prose too — SETUP.md's bootstrap
    `rm` line and UPGRADING.md's cleanup step. Adding a file to `_MAINTAINER_ONLY`
    without updating those leaves it shipped into every bootstrapped project.

    Anchored on the *path* form (`_framework/future-work.md`), not the bare
    filename: an enumeration of the set spells out real paths, while ordinary
    prose — a release note recalling an old fix — names the file bare. That
    distinction keeps historical mentions from tripping the check.
    """
    problems: list[str] = []
    for rel in ("SETUP.md", "UPGRADING.md"):
        path = repo_root / rel
        if not path.is_file():
            continue  # bootstrap removes both — nothing to check downstream
        try:
            text = " ".join(path.read_text(encoding="utf-8").split())
        except OSError:
            continue
        anchor = "_framework/future-work.md"
        start = 0
        while (i := text.find(anchor, start)) != -1:
            window = text[max(0, i - 250): i + 250]
            missing = [n for n in _MAINTAINER_ONLY if n not in window]
            if missing:
                problems.append(
                    f"{rel}: the maintainer-only list near offset {i} omits "
                    f"{', '.join(missing)} — add them, or they ship into every "
                    f"bootstrapped project."
                )
            start = i + 1
    return problems


# The `framework` remote is added by two documents — UPGRADING.md Step 0 and
# `/framework update` — and is **fetch-only**: the template is upstream, and no
# project ever pushes to it. `git push framework main` from a live project would
# publish that project's entire kb into the shared template repo, and it is one
# tab-completion away from the `git fetch framework` the runbook asks for. Both
# sites therefore disable the push URL, which also makes the asymmetry visible in
# `git remote -v`. This check keeps a third site (or an edited one) from adding
# the remote without the guard.
_REMOTE_ADD = "git remote add framework"
_REMOTE_GUARD = "git remote set-url --push framework DISABLED"

# Files that may legitimately add the remote. Deliberately not every doc: a live
# project's own notes may *mention* the command, and this check ships downstream.
# Within them, only fenced command blocks count — see `_fenced_blocks`.
_REMOTE_ADD_SITES = ("SETUP.md", "UPGRADING.md", ".claude/skills/framework/SKILL.md")


def _fenced_blocks(text: str) -> list[tuple[int, list[str]]]:
    """Yield (first-line-number, lines) for each ``` fenced block in a markdown
    file. Only a fenced block is a command an agent runs; the same command named
    in prose — a release note recalling this very fix — is not."""
    blocks: list[tuple[int, list[str]]] = []
    current: list[str] | None = None
    start = 0
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            if current is None:
                current, start = [], n + 1
            else:
                blocks.append((start, current))
                current = None
            continue
        if current is not None:
            current.append(line)
    if current is not None:  # unterminated fence — treat what we have as a block
        blocks.append((start, current))
    return blocks


def check_framework_remote_is_push_disabled(repo_root: Path) -> list[str]:
    """Wherever a command block adds the `framework` remote, the same block must
    disable its push URL."""
    problems: list[str] = []
    for rel in _REMOTE_ADD_SITES:
        path = repo_root / rel
        if not path.is_file():
            continue  # bootstrap removes SETUP.md/UPGRADING.md — skip downstream
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for start, lines in _fenced_blocks(text):
            block = "\n".join(lines)
            if _REMOTE_ADD not in block or _REMOTE_GUARD in block:
                continue
            offset = next(
                i for i, line in enumerate(lines) if _REMOTE_ADD in line
            )
            problems.append(
                f"{rel}:{start + offset} adds the `framework` remote without "
                f"`{_REMOTE_GUARD}` in the same command block — the remote is "
                f"fetch-only, and a push to it would publish a project's kb "
                f"into the template repo."
            )
    return problems


_CHECKS = (
    check_config_matches_rules,
    check_no_dangling_maintainer_refs,
    check_maintainer_only_enumerations_agree,
    check_version_matches_latest_release,
    check_framework_remote_is_push_disabled,
)


def run_all(repo_root: Path) -> list[str]:
    """Run every hard-edge check. Returns a flat list of problem strings ([] == clean)."""
    problems: list[str] = []
    for check in _CHECKS:
        problems.extend(check(repo_root))
    return problems


def main() -> int:
    try:
        repo_root = find_repo_root()
    except RuntimeError as e:
        print(f"framework-check: {e}", file=sys.stderr)
        return 2
    problems = run_all(repo_root)
    if not problems:
        print("framework-check: clean.")
        return 0
    print(f"framework-check: {len(problems)} problem(s):")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
