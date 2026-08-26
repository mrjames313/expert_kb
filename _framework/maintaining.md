# Maintaining the framework

Author-facing notes for evolving the Expert Coordination framework itself. This file and `future-work.md` are **template-repo-only**: SETUP.md removes both during bootstrap, so they never ship into a live project.

## Keep spec.md in sync with reality

`_framework/spec.md` is the maximal specification, but **nothing enforces it**: no tool parses it, and it's in no role preload (agents read it on demand, section by section). So it drifts silently — the only guard is discipline. Whenever a change lands, update spec.md in the *same* commit:

| If you change… | Update in spec.md | And also |
|---|---|---|
| a file/dir under `_framework/` (tool, schema doc, hook, lint-rule module) | §2 directory-layout tree + §2 file-maintenance table | — |
| a capability (add / rename / behavior) | §3 Capabilities | `_framework/schema/capabilities.md`, `_framework/schema/claude-snippets/<cap>.md`. **Snippet/`# capability:` content changes reach live projects only when they run `/framework resync` — the upgrade runbook (Step 4) does this, but call out a behavioral change in the `UPGRADING.md` release note so it isn't missed.** |
| a skill (add / remove / trigger) | §15 Skills | ship `.claude/skills/<name>/SKILL.md`. If it's **always-available**, add it to `capabilities.md` → "Always-available skills" (the single source of truth — role files reference it, so do **not** edit role files). If it's **capability-gated**, add it to that capability's "Role file edits" list and snippet. |
| a lint rule | §14 Lint rules | `_framework/schema/lint-rules.md`, `_framework/tools/lint_rules/rule_*.py` |
| frontmatter / types / lifecycle | §5 Frontmatter | `_framework/schema/frontmatter.md` |
| link / promotion / exchange / commons-extension rules | §13 / §16 / §12 (+ the protocol) | matching `_framework/schema/*-protocol.md` |
| the bootstrap flow | `SETUP.md` | "Building / refreshing the template" below |
| role-file structure (`role-template.md`) | — | `SETUP.md`'s role-authoring bullets **duplicate** the template inline (boundaries, allowed skills, default behaviors), so they drift when the template changes. Keep them in sync — better, have SETUP defer to the template ("fill in per `role-template.md`") rather than re-list its content. This is how the "reference the skill baseline, don't enumerate it" change reached `role-template.md` but not `SETUP.md`. |

Rule of thumb: if a change would make the §2 tree or any protocol section wrong, the change isn't done until spec.md is fixed too. Treat spec.md as documentation that must be re-derived from reality — nothing else will catch the drift.

**Don't reference template-only files from pulled docs.** `SETUP.md`, `UPGRADING.md`, `_framework/future-work.md`, and `_framework/maintaining.md` are deleted at bootstrap (SETUP.md Step 6) and are *not* pulled on upgrade, so a live project never has them. A pulled doc (`spec.md`, `_framework/schema/*.md`, `CLAUDE.md`, `.claude/skills/*`) that links one by local path leaves a dangling reference in every project. Keep such statements self-contained (say "tracked in the framework repo's backlog", not "see `future-work.md`"). This is a grep-checkable edge — a natural first hard check for the doc-dependency-graph idea in `future-work.md`.

## Skills must match their schema docs

Skills (`.claude/skills/*/SKILL.md`) are runbooks that implement the schema docs (`_framework/schema/*.md`, `CLAUDE.md`, the spec-template). Nothing enforces their agreement, and when they drift the *skill* is what an agent actually follows — so a skill that contradicts its schema causes real damage. CLAUDE.md tells agents "schema wins," but that only helps if they cross-check.

- When you change a protocol, update **every skill that implements it** in the same commit.
- When you change a skill, confirm it still matches its schema.
- On a disagreement, fix the side that drifted — usually the skill, occasionally the schema. Corroborate against the tool behavior and sibling skills, not just the schema doc: e.g. "leave the source unchanged" on promotion is confirmed by `promote.py` never touching the area page and by `link-conventions.md` making superseded-links an error.

## Releasing a framework change (bump the version, write the migration)

`framework_version` in `_framework/config.yml` is the date downstream projects gate *migrations*
on. Two distinct things can go wrong, so a release needs two artifacts:

- **Missing `UPGRADING.md` release block** → the migration doesn't exist, so downstream never
  learns of a required data change. (Code files themselves still arrive — Step 3 pulls them
  unconditionally — so *code-only* fixes reach projects regardless. This gap bites only
  changes that need a data migration, like 5c/5d's optional twin backfill.)
- **Missing version bump** → projects can't record that they reached this release, so
  idempotent migrations re-run on every future update and the version marker drifts, mis-gating
  later migrations.

Both were missed for the 5c/5d and commons-id changes; the checklist below is the guard.

**Trigger — did you change *pulled* machinery?** A release is required whenever a push to
`main` touches anything `/framework update` pulls (see UPGRADING.md Step 3–4):
`_framework/schema/`, `_framework/tools/`, `_framework/hooks/`, `_framework/spec.md`,
`_framework/adoption-guide.md`, `.claude/skills/`, `CLAUDE.md`, or `.claude/settings.json`.
Changes to **non-pulled** files alone — `_framework/config.yml` capabilities,
`future-work.md`, `maintaining.md`, `commons/`, `areas/`, `exchanges/` — do **not** require a
release.

**Definition of done for a releasing change (same commit / branch as the change):**

1. **Bump** `framework_version` in `_framework/config.yml` to **today's date** (`YYYY-MM-DD`).
   Versioning is date-based and per-release: several pushes on one day share that date and
   append to the same release section — do not invent sub-versions.
2. **Write the migration** in `UPGRADING.md` Step 5: add (or append to) a `**Release <today>**`
   block. State the downstream action for each change, or say it explicitly needs none —
   *"code-only, takes effect on pull in Step 4."* Every releasing change gets a line, even a
   no-action one, so the list is a complete ledger.
3. **Sync the docs** per the two sections above (spec.md; schema docs; skills). Already
   required, restated here so "done" means all of it.
4. **Run the hard-edge checks:** `python _framework/tools/framework_check.py`. It mechanically
   verifies the derived-vs-source invariants that kept drifting — config `warnings_visible` ==
   shipped warning rules, no pulled doc references a maintainer-only file, and
   `framework_version` == the latest `UPGRADING.md` release. Fix anything it flags before
   pushing. (Not exhaustive — it covers the *checkable* edges; see the doc-dependency-graph
   item in `future-work.md` for the rest.)

Rule of thumb: **pulled machinery changed → the change isn't done until `config.yml` and
`UPGRADING.md` are updated in the same branch.** If you catch an unreleased change after the
fact (framework machinery changed since the last version bump, but no matching `**Release**`
block exists), treat it as a bug and backfill both — as we did on 2026-08-15.

## Every requirement clause needs an enforcer or a backfill

A schema clause that *adds a requirement* ("promotion files an INBOX ack", "commons pages are curated for a commons reader", "roles reference the baseline skill set") is inert unless something detects its violation. The recurring bug this session — six instances — was a documented behaviour with no implementation: the clause reads as done, but nothing catches a page that doesn't satisfy it, so `lint: clean` asserts nothing about it and the gap accumulates silently.

Rule: **when you add or change a requirement clause, name — in the same change — either (a) the tool/lint rule that enforces it, or (b) the manual backfill item** (an `UPGRADING.md` release entry telling existing projects what to fix). If it can be neither enforced nor backfilled (e.g. a judgment-based content requirement like "strip resolved-deliberation cruft"), say so explicitly in the clause, so a reader knows it's advisory rather than assuming a checker exists. A documented backstop that doesn't exist is worse than none — it's the stated reason the primary mechanism "isn't critical."

This generalizes the release discipline above: the version bump makes machinery *arrive*; this makes a new requirement *observable*.

## Building / refreshing the template

1. Create the template repo with `_framework/` populated, plus empty `commons/` and `areas/` skeletons. Write `CLAUDE.md` (always-on sections only), `_framework/config.yml` with initial state (all four capabilities off; all warnings shadowed).

2. Write the deterministic Python tools under `_framework/tools/` — `lint.py` (plus the `lint_rules/` modules), `pulse_compact.py`, `promote.py`, `manifest_validate.py`, `commons_extension.py`, `activity_days.py`, `token_estimate.py`, `telemetry.py`, and `framework.py`, with shared helpers in `common.py`.

3. Write the always-available skills as `.claude/skills/<name>/SKILL.md` with explicit trigger language. Write the capability-gated skills too — all skills ship with the template; the `framework` skill manages activation state via `config.yml`.

4. Write `_framework/schema/capabilities.md` and the four snippet files in `_framework/schema/claude-snippets/` (one per capability) declaratively describing what each enable/disable operation does.

5. Pick one project to instantiate. Write `commons/brief.md`. Pick 2 areas to start. Write area `brief.md` and one role per area.

6. **Pre-created at setup**: `INBOX.md` (empty), `areas-index.md` (lint populates), `roles/<role>/role.md` per area, `raw/` per area (empty subdirs), `kb/` per area (empty subdirs), `pulse.md` per area (empty template), `_journal/pulse.log` per area (empty). **On-demand**: exchanges (`/exchange` bootstraps), specs (`/plan` bootstraps), `_proposed/` entries (`/propose-promotion` bootstraps), POR files (when `/framework enable por` runs).

7. Run one end-to-end exercise: ingest 2–3 sources, run one spec brief → outcome, propose a finding to commons, promote it.

8. As the project grows, enable capabilities as signals appear. The framework skill handles all the mechanics.

## Open design questions

**Pulse line cap.** Default 80 lines. Reasonable across areas, or do some areas need different caps?

**Auto-debug retry limit.** Default 2 rejections before auto-debug fires (applies when `formal_review` on).

**Cross-area specs.** Default: spec lives under the area that owns the outcome; coordination via exchanges. Alternative: top-level `cross-area-specs/`. I'd avoid the alternative unless we find we need it.

**Sub-area POR.** Default: include but allow it to be a stub or omitted with a parent-POR note.

**Manifest type.** Marked `type: source`. Could add `type: data` if friction emerges.

**Raw subdirectory structure.** Suggested `papers/`, `articles/`, `transcripts/`, `web/`. Areas can add subdirs as needed; framework doesn't constrain.

**Shadow trigger threshold.** Default 5 findings before suggesting enable. Tunable in `config.yml`.

---

Deferred feature ideas with "revisit when" triggers live in `future-work.md`.
