# Framework Tools

Deterministic Python helpers used by the framework. Run from the repo root.

## Setup

Requires Python 3.10+.

The recommended approach is a venv at the repo root so dependencies stay local to the project:

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r _framework/tools/requirements.txt
```

For running the test suite, install the dev extras instead (they pull in `requirements.txt` plus pytest):

```bash
pip install -r _framework/tools/requirements-dev.txt
```

If you'd rather not use a venv, install globally with `--break-system-packages` (on systems that require it):

```bash
pip install -r _framework/tools/requirements.txt
# or requirements-dev.txt if you'll run the tests
```

In either case, activate the venv before invoking the tools, or run them via `./.venv/bin/python _framework/tools/lint.py`.

## Tools

### `lint.py` — knowledge-base linter

Runs all enabled lint rules and reports findings. See `_framework/schema/lint-rules.md` for the rule catalogue.

```bash
python _framework/tools/lint.py            # run all rules
python _framework/tools/lint.py --rule 01  # run only rule 01
python _framework/tools/lint.py --json     # machine-readable output
```

Exit codes: `0` no findings, `1` errors, `2` warnings only (when warning rules land), `3` lint runner setup error.

Implemented (correctness errors):
- Rule 1 — Frontmatter validity
- Rule 2 — Forward-link integrity (body + frontmatter wikilinks, area prefixes, provenance.raw_path)
- Rule 3 — Backlink synchronization (fixup; writes `.links.json` sidecars)
- Rule 5 — Supersession integrity
- Rule 6 — Type-specific completeness
- Rule 7 — Pulse size
- Rule 12 — Data manifest integrity
- Rule 15 — Index maintenance (fixup; regenerates `areas-index.md` and `kb/index.md`)
- Rule 17 — Raw immutability
- Rule 18 — Page ID uniqueness across the project

Deferred: configurable warnings (Rule 4, 8, 9, 10, 11, 13, 14, 16) and a maintenance-category rule (Rule 19 or later).

### `framework.py` — capability and lint visibility engine

Enable/disable framework capabilities, manage lint warning visibility, and view current state. Used by the `/framework` skill.

```bash
python _framework/tools/framework.py                            # show full status
python _framework/tools/framework.py status                     # same
python _framework/tools/framework.py lint-status                # just lint visibility
python _framework/tools/framework.py --dry-run enable por       # preview the plan
python _framework/tools/framework.py enable multi_area          # apply
python _framework/tools/framework.py disable formal_review      # disable
python _framework/tools/framework.py enable-lint rule_4_orphans # show shadow rule
python _framework/tools/framework.py disable-lint 4             # short form
python _framework/tools/framework.py --json enable por          # machine-readable
python _framework/tools/framework.py prune                      # list stale preload entries
python _framework/tools/framework.py prune researcher           # restrict to one role
python _framework/tools/framework.py prune --apply              # apply removals
```

What enable/disable does, depending on the capability:

- **multi_area** — splices a section into CLAUDE.md; adds exchange-related boundaries and skills to every role file.
- **por** — splices a section into CLAUDE.md; creates `commons/POR.md`, `areas/<area>/POR.md` for each existing area, and `commons/roles/coordinator/role.md`; adds POR entries to each role's preload (own area + parents for sub-areas).
- **task_subagents** — splices a section into CLAUDE.md only (the behavior change is in `/implement`).
- **formal_review** — splices a section into CLAUDE.md; creates a reviewer variant of each implementer role; adds `review` skill to implementer roles. Requires `task_subagents` to be enabled first.

On disable, the CLAUDE.md section is removed, role file edits are reverted, and capability-specific files are deleted (coordinator role, reviewer roles). POR.md files persist on disk but become inert; the warning surfaces this. Disable is blocked if another enabled capability depends on the one being disabled (e.g., disabling `task_subagents` while `formal_review` is on).

`prune` finds preload entries that should be candidates for removal, on two signals:

- **Lifecycle**: the target kb page has `status` in `{superseded, falsified, dropped}` — dead weight in any role's preload.
- **Activity** (when enough telemetry exists): the entry has not been cited across the last N completed sessions for the role. Thresholds are in `config.yml` under `prune.full_tier_stale_sessions` (default 10) and `prune.frontmatter_tier_stale_sessions` (default 30). With fewer than N sessions of history, activity-based candidates are not produced.

Entries inside `# capability: X` blocks are flagged for visibility but skipped on `--apply` — those are framework-managed and should be removed via `disable` instead.

Exit codes: 0 OK, 1 plan error (e.g., unmet dependency, unknown capability), 2 apply error, 3 setup error.

### `pulse_compact.py` — wrap-up compaction

Materializes pulse.log events into pulse.md and truncates the log. Regenerates the auto-derived sections (recent decisions, active concepts, recent findings) from current kb state; preserves human-edited sections (current focus, open questions) and updates them from log entries.

```bash
python _framework/tools/pulse_compact.py                  # compact all (commons + every area)
python _framework/tools/pulse_compact.py areas/research   # compact one area
```

Idempotent: running with an empty log is a no-op. Exits non-zero if any pulse.md exceeds the line cap after compaction.

### `promote.py` — proposal → commons

Moves a page from `commons/_proposed/<slug>/page.md` to `commons/kb/<type>/<new-commons-id>.md`, updating frontmatter (`id` → `<prefix>-commons-<slug>`, `area: commons`, `human_reviewed: false`, `promoted_from_page`, `promoted_from_area`, `promoted_on`, `promotion_path`; drops `relevant_to`) and writing a CHANGELOG entry. The source area page is left unchanged; the proposal directory remains as audit trail (only its `page.md` moves).

```bash
python _framework/tools/promote.py 2026-05-shot-noise
```

Errors cleanly when the target already exists, the proposal is missing, or the frontmatter is invalid.

### `manifest_validate.py` — single-manifest validator

Focused inspector for a single data manifest. Same checks as lint Rule 12 (provenance, storage_uri, context_pages) but scoped to one file with prose output.

```bash
python _framework/tools/manifest_validate.py areas/research/data/manifests/m-2026-05-test.md
python _framework/tools/manifest_validate.py areas/research/data/manifests/m-2026-05-test.md --json
```

### `token_estimate.py` — preload token-cost estimator

Estimates the token cost of loading a role's preload list (both full and frontmatter tiers). Used by `/budget` to identify heavy roles and by the telemetry layer to record per-session preload cost.

```bash
python _framework/tools/token_estimate.py areas/research/roles/researcher/role.md
python _framework/tools/token_estimate.py areas/research/roles/researcher/role.md --json
```

The estimate is character-count-based (chars / 4). Accurate enough for relative comparisons (which is what `/budget` and `/framework prune` actually need); not a substitute for Claude Code's `/context` for exact runtime numbers.

### `telemetry.py` — per-session event log

Writes session events to `_framework/telemetry/sessions.jsonl` (git-ignored). Each session generates two events: a `session_start` with the preload estimate and a `session_end` with citation/load data.

```bash
# Recorded by the start skill when it adopts a role
python _framework/tools/telemetry.py session-start --role areas/research/roles/researcher/role.md

# Recorded by /wrap-up or the session-end hook
python _framework/tools/telemetry.py session-end \
    --cited "areas/research/kb/findings/f-1.md,areas/research/kb/concepts/c-3.md" \
    --loaded "areas/research/kb/concepts/c-4.md"

# Inspect recent sessions
python _framework/tools/telemetry.py recent --n 10
python _framework/tools/telemetry.py recent --n 10 --json
```

The telemetry log feeds `/budget` (per-role trends, heavy paths) and `/framework prune` (stale-preload detection based on citation history). Both consumers will land in later commits.

### `activity_days.py` — git-log-derived active days

Helper used by lint and other tools for activity-based thresholds.

```bash
python _framework/tools/activity_days.py --since 2026-01-01
python _framework/tools/activity_days.py --back 30    # calendar date 30 active days ago
```

## Tests

```bash
cd _framework/tools
python -m pytest tests/ -q
```

Tests cover each rule module's pass case and per-violation cases, plus `activity_days`, `token_estimate`, and `telemetry` edge cases (empty repo, cold-project resumption, role file outside repo root, unpaired session_end, etc.).

## Architecture

Each lint rule lives in `lint_rules/rule_NN_<name>.py` and exposes a single function:

```python
def check(repo_root: Path, config: dict) -> list[Finding]:
    """Run this rule. Return list of findings."""
```

`lint.py` runs fixup rules first (rules 3 and 15, which write files), then inspection rules. Shared utilities are in `common.py`. Tests share fixtures from `tests/conftest.py` and `tests/lint_helpers.py`.

`token_estimate.py` and `telemetry.py` are standalone but interoperate: telemetry calls `estimate_role_preload` when recording a session start.

The lint tools have no dependencies on Claude or any LLM — they're pure Python with PyYAML and stdlib only.
