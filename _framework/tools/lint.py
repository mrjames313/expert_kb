#!/usr/bin/env python3
"""
Lint runner — dispatches to per-rule modules in _framework/tools/lint_rules/.

Phases:
1. Fixup rules first — they modify files (sidecars, indices).
2. Inspection rules — read-only, produce findings.

Exit codes:
- 0: no findings
- 1: errors (always shown)
- 2: warnings only (note: warning rules will arrive in commit 2b)

Usage:
    python lint.py              # run all rules; print findings
    python lint.py --json       # output JSON instead of human-readable
    python lint.py --rule N     # run only rule_NN
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

# Ensure tools dir is on sys.path so rule modules can import `common`, etc.
TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from common import Finding, find_repo_root, load_config  # noqa: E402

# Rule modules in the fixup phase: these write files.
FIXUP_RULES = [
    "rule_03_backlinks",
    "rule_15_index",
]

# Inspection rules: read-only.
INSPECTION_RULES = [
    "rule_01_frontmatter",
    "rule_02_forward_links",
    "rule_05_supersession",
    "rule_06_completeness",
    "rule_07_pulse_size",
    "rule_12_manifest",
    "rule_17_raw_immutability",
    "rule_18_id_uniqueness",
    "rule_20_commons_drift",         # warning; self-gates on warnings_visible
    "rule_21_commons_twin_links",    # warning; self-gates on warnings_visible
]

ALL_RULES = FIXUP_RULES + INSPECTION_RULES


def _load_rule(name: str):
    """Import a rule module by name from lint_rules/."""
    return importlib.import_module(f"lint_rules.{name}")


def _run_rules(rule_names: list[str], repo_root: Path, config: dict) -> list[Finding]:
    findings: list[Finding] = []
    for name in rule_names:
        try:
            module = _load_rule(name)
            findings.extend(module.check(repo_root, config))
        except Exception as e:  # noqa: BLE001
            # A rule crashed; report it as a meta-finding rather than failing the run.
            findings.append(
                Finding(
                    rule_id=name,
                    severity="error",
                    file_path="<lint>",
                    message=f"rule crashed: {type(e).__name__}: {e}",
                )
            )
    return findings


def _print_findings(findings: list[Finding], *, use_color: bool) -> None:
    if not findings:
        print("lint: clean.")
        return

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    for f in findings:
        print(f.format(color=use_color))
        print()

    summary = []
    if errors:
        summary.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
    if warnings:
        summary.append(f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}")
    print(f"lint: {', '.join(summary)}.")


def _print_json(findings: list[Finding]) -> None:
    payload = [
        {
            "rule_id": f.rule_id,
            "severity": f.severity,
            "file_path": f.file_path,
            "line": f.line,
            "message": f.message,
            "suggestion": f.suggestion,
        }
        for f in findings
    ]
    print(json.dumps(payload, indent=2))


def _exit_code(findings: list[Finding]) -> int:
    if any(f.severity == "error" for f in findings):
        return 1
    if any(f.severity == "warning" for f in findings):
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lint over the expert_kb repo.")
    parser.add_argument(
        "--rule",
        help="run only this rule (module name, e.g. rule_01_frontmatter, or short form 01)",
    )
    parser.add_argument("--json", action="store_true", help="output JSON instead of text")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color output")
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="path to repo root (default: auto-detect from cwd)",
    )
    args = parser.parse_args()

    try:
        repo_root = args.repo.resolve() if args.repo else find_repo_root()
    except RuntimeError as e:
        print(f"lint: {e}", file=sys.stderr)
        return 3

    try:
        config = load_config(repo_root)
    except RuntimeError as e:
        print(f"lint: {e}", file=sys.stderr)
        return 3

    if args.rule:
        # Allow short form like "01" or full "rule_01_frontmatter"
        target = args.rule
        if target.isdigit():
            target = f"rule_{int(target):02d}"
        matches = [name for name in ALL_RULES if name.startswith(target)]
        if not matches:
            print(f"lint: no rule matches {args.rule!r}", file=sys.stderr)
            return 3
        rules_to_run = matches
    else:
        rules_to_run = ALL_RULES

    findings = _run_rules(rules_to_run, repo_root, config)

    if args.json:
        _print_json(findings)
    else:
        _print_findings(findings, use_color=(not args.no_color) and sys.stdout.isatty())

    return _exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
