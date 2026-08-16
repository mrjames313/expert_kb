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

### Rule 18 — Page ID uniqueness

Every kb page's `id` must be unique across the project (commons + all areas). Duplicate ids make wikilinks ambiguous and break backlink/forward-link integrity. (The originally-planned maintenance-category rule is deferred to Rule 19+.)

## Configurable-visibility rules (warnings)

These rules are **off by default** and enabled per project via `/framework enable-lint <rule>`. A disabled rule **self-gates** — it returns no findings (see "Warning visibility" below).

**Implemented vs. planned.** Only rules with a shipped module under `_framework/tools/lint_rules/` (a `SEVERITY = "warning"` module exposing a `CONFIG_KEY`) are real; today that is **Rules 20 and 21**. Rules 4, 8, 9, 10, 11, 13, 14, and 16 below are **design sketches, not yet implemented** — `/framework enable-lint` derives its accepted set from the shipped modules, so it rejects them until they ship (this derivation is what keeps the enabler from drifting out of sync with the rules, as it once did). When you implement one, its module's `CONFIG_KEY` makes it enable-able automatically; add the key to the template `config.yml` and drop the "(planned)" marker here.

### Rule 4 — Orphan detection (planned)

Pages with zero `links_in`. May indicate isolated content or just index-page leaves; meaningful or not depends on project.

### Rule 8 — Stale concept warning (planned)

`concept` with `status: under_test` older than `stale_concept_threshold_active_days` (default 30) — may indicate the test is stuck or forgotten.

### Rule 9 — Cross-area link threshold (planned)

Pages linking to 3 or more distinct areas earn a warning suggesting the topic belongs in commons (via promotion) or in an exchange (with `multi_area` enabled). Pages with `area: commons` are exempt.

### Rule 10 — Promotion freshness (planned)

Commons pages with `human_reviewed: false` older than `promotion_freshness_active_days` (default 14) surface to INBOX as overdue ack.

### Rule 11 — Spec hygiene (planned)

Specs with tasks in non-terminal status older than `spec_abandonment_active_days` (default 60) surface as potentially abandoned.

### Rule 13 — Backlinker freshness (planned)

For each page, identify `links_out` targets updated more recently than the page itself. Flag as candidates for content-consistency review.

### Rule 14 — Exchange staleness (planned)

Exchanges with `status: open` older than `exchange_stale_active_days` (default 7) surface to INBOX. Only runs when `multi_area` is enabled.

### Rule 16 — Cross-area read pattern (planned)

When a task's Implementation Notes show many full-page reads of another area's kb, suggest an exchange would have been a better path. Off by default; enable when the pattern becomes a real concern.

### Rule 20 — Commons drift

A commons page whose area source's `updated` is newer than the commons page's `aligned_on` — the two have diverged since they were last reconciled. Reconcile via `/amend-commons`. Detection is timestamp-based; the source change may not actually affect the commons copy, hence a warning.

A commons page the rule **cannot** drift-check — missing `promoted_from_page`, missing `aligned_on`, or a `promoted_from_page` that resolves to no kb page — is itself surfaced as a warning ("cannot check for drift: …"), never silently skipped. A silent skip would be a false negative: an enabled rule reporting `lint: clean` while covering zero pages reads as "commons is reconciled" when it was never checked. These findings double as the backfill worklist after an upgrade (see `UPGRADING.md`).

### Rule 21 — Commons twin-link preference

A commons page that cites an area page which has a commons twin — prefer the twin so commons stays self-contained and project-wide backlinks land on the twin. Occasional cross-area reads are acceptable, so this is a nudge, not an error.

## Activity-based thresholds

All time thresholds use git-log-derived active days, computed via `_framework/tools/activity_days.py`:

```bash
git log --since=<event_date> --pretty=format:%ad --date=short | sort -u | wc -l
```

A cold project doesn't generate spurious warnings — when you return after a break, aging resumes from your return.

For in-flight events not yet committed (e.g., `_journal/pulse.log` entries), the entry's timestamp is used.

## Warning visibility (current behavior)

A configurable-visibility rule is **off by default** and **self-gates**: when its `lint.warnings_visible.<rule>` flag is false it returns no findings. Enable it with `/framework enable-lint <rule>`.

The originally-designed *shadow* behavior — run every rule silently, accumulate trigger counts, and suggest enabling one past `shadow_suggest_threshold` — is **not implemented and under reconsideration** (it may add noise without clear value; see `future-work.md`). Until that's decided, `shadow_suggest_threshold` in `config.yml` is inert, and only Rules 20–21 are implemented among the configurable set.
