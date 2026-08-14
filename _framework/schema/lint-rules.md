# Lint Rules

The linter (`_framework/tools/lint.py`) is deterministic Python — no LLM in the loop. It runs on demand via `/check` and at the end of every `/wrap-up`.

**All rules always run.** What changes per configuration (`_framework/config.yml`) is whether findings are *visible* (displayed and acted on) or *shadowed* (counted internally; surfaced as suggestions when frequent).

## Always-visible rules (correctness errors)

These rules cannot be silenced — they catch structural problems that break the framework's invariants.

### Rule 1 — Frontmatter validity

Required fields present. `type` is one of `source`, `concept`, `finding`, `decision` (or `por` for POR files). `status` is valid for the type. Dates are ISO 8601. IDs match the `<type-prefix>-<date>-<slug>` convention.

### Rule 2 — Forward-link integrity

Every `[[wikilink]]` resolves to an existing page — in the page **body and in frontmatter values** (`evidence`, `provenance.ref`, `alternatives_considered`, `superseded_by`, …). Frontmatter links are checked because tools that re-serialize frontmatter can corrupt them silently.

A link may carry an area prefix (`[[area:target]]`, e.g. `[[research:findings/f-…]]`). When present, the prefix must name the target's actual area, or it's an error. See `link-conventions.md`.

Every relative markdown link to a repo path resolves to an existing file.

Source pages: `provenance.raw_path` must resolve to an existing file in `raw/` (when populated).

### Rule 3 — Backlink synchronization

For every forward link A→B, B's `.links.json` sidecar lists A in `links_in`. Automatically maintained — lint regenerates sidecars rather than failing.

### Rule 5 — Supersession integrity

Pages with `status: superseded` must have `superseded_by` populated.

Forward links to pages with `status: superseded` are errors; the linter suggests the replacement via `superseded_by`.

### Rule 6 — Type-specific completeness

- `concept` with `status: under_test`, `supported`, or `falsified` must have a non-empty `evidence` list.
- `finding` must have `provenance` populated.
- `decision` must have `alternatives_considered` populated (may be empty list).

### Rule 7 — Pulse size

`pulse.md` exceeding the line cap (default 80) is an error. The `wrap-up` skill is responsible for promoting or dropping content to fit — silent truncation is forbidden.

### Rule 12 — Data manifest integrity

Each manifest in `data/manifests/` has `provenance`, `storage_uri`, and a `context_pages` link list pointing into `kb/`.

### Rule 15 — Index maintenance

The linter regenerates `areas-index.md` (from area briefs and role summaries) and each `kb/index.md` (from page frontmatter in that directory) on every run.

### Rule 17 — Raw immutability

Detect modifications to files in `raw/` after their initial commit. Raw materials are **immutable once added**: existing files must never be edited or deleted.

New raw materials may be added at any time (typically via `/ingest`, which creates both the raw file and its source-summary page in `kb/sources/`). Lint distinguishes additions (allowed) from modifications (errors) by checking git status — files whose initial commit was the current commit are fine; files with subsequent edits trigger the rule.

### Rule 18 — Maintenance category violations

Detect writes by agents to human-authored files outside designated workflows (e.g., an agent rewriting `CLAUDE.md`, a role file, or a schema doc outside `/framework enable`/`disable`).

## Configurable-visibility rules (warnings)

These rules can be made visible per project via `/framework enable-lint <rule>`. When disabled, they run in shadow mode — findings are counted and surface as suggestions if they exceed `shadow_suggest_threshold` (default 5).

### Rule 4 — Orphan detection

Pages with zero `links_in`. May indicate isolated content or just index-page leaves; meaningful or not depends on project.

### Rule 8 — Stale concept warning

`concept` with `status: under_test` older than `stale_concept_threshold_active_days` (default 30) — may indicate the test is stuck or forgotten.

### Rule 9 — Cross-area link threshold

Pages linking to 3 or more distinct areas earn a warning suggesting the topic belongs in commons (via promotion) or in an exchange (with `multi_area` enabled). Pages with `area: commons` are exempt.

### Rule 10 — Promotion freshness

Commons pages with `human_reviewed: false` older than `promotion_freshness_active_days` (default 14) surface to INBOX as overdue ack.

### Rule 11 — Spec hygiene

Specs with tasks in non-terminal status older than `spec_abandonment_active_days` (default 60) surface as potentially abandoned.

### Rule 13 — Backlinker freshness

For each page, identify `links_out` targets updated more recently than the page itself. Flag as candidates for content-consistency review.

### Rule 14 — Exchange staleness

Exchanges with `status: open` older than `exchange_stale_active_days` (default 7) surface to INBOX. Only runs when `multi_area` is enabled.

### Rule 16 — Cross-area read pattern

When a task's Implementation Notes show many full-page reads of another area's kb, suggest an exchange would have been a better path. Off by default; enable when the pattern becomes a real concern.

## Activity-based thresholds

All time thresholds use git-log-derived active days, computed via `_framework/tools/activity_days.py`:

```bash
git log --since=<event_date> --pretty=format:%ad --date=short | sort -u | wc -l
```

A cold project doesn't generate spurious warnings — when you return after a break, aging resumes from your return.

For in-flight events not yet committed (e.g., `_journal/pulse.log` entries), the entry's timestamp is used.

## Shadow run behavior

When a rule is shadowed, the linter still evaluates it but doesn't display findings in the standard report. Instead, the linter accumulates trigger counts and adds a suggestion section at the bottom:

```
Disabled lint rules with significant findings:
  Rule 4 (orphans) — 12 findings
  Rule 11 (spec abandonment) — 3 findings

Consider enabling: /framework enable-lint rule_4
```

A rule's findings surface as a suggestion when the trigger count meets `shadow_suggest_threshold` (default 5).
