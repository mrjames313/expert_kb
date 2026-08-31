# Upgrading: Expert Coordination framework

The canonical upgrade runbook for an already-instantiated project. It always lives at
https://github.com/mrjames313/expert_kb/blob/main/UPGRADING.md — treat *that* copy as
authoritative, never a local one.

**For humans:** in your project, launch Claude Code and tell it:

> Follow the upgrade instructions at https://github.com/mrjames313/expert_kb/blob/main/UPGRADING.md

Or, if your project is new enough to have it, run `/framework update` — it fetches and
follows this file for you.

---

## For the agent following this guide

You are upgrading an existing project to the latest framework. **Preserve all project
content; replace only framework machinery; run the migrations for anything introduced
since the project's `framework_version`.**

### Step 0: Use the latest instructions, not a stale copy

If you are reading a local copy, fetch the newest one and follow *that* instead:

```bash
git remote add framework https://github.com/mrjames313/expert_kb.git 2>/dev/null || true
git fetch framework
git show framework/main:UPGRADING.md
```

Follow the fetched version from here on — the steps below may have changed since this copy.
`git show` *prints* this file; it is never written into your project, so a live project keeps
no local `UPGRADING.md` and there is nothing here to delete when you finish.

### Step 1: Require a clean, committed tree (rollback safety)

Do not start until the working tree is clean:

```bash
git status --porcelain
```

If that prints **anything**, stop and have the user commit (or stash) first. A clean,
committed tree is what makes the upgrade reversible: if anything goes wrong you can restore
the exact pre-upgrade state by discarding the upgrade branch. Do not proceed otherwise.

### Step 2: Work on an upgrade branch

```bash
git checkout -b framework-upgrade
```

### Step 3: Pull framework files (never project content)

```bash
git checkout framework/main -- \
  _framework/schema _framework/tools _framework/hooks \
  _framework/spec.md _framework/adoption-guide.md .claude/skills
```

**Do not** pull these — they are per-project state or content:
`_framework/config.yml`, `commons/`, `areas/`, `exchanges/`, `INBOX.md`, `areas-index.md`,
any `kb/index.md`, `_journal/`, and role files. Author/template-only files
(`SETUP.md`, `UPGRADING.md`, `_framework/future-work.md`, `_framework/maintaining.md`) are
not part of a live project and this pull does not add them; in the normal case none are
present. Step 5's cleanup migration removes any stale leftovers from a pre-cleanup bootstrap.

Review before continuing: `git diff --staged`.

### Step 4: Reconcile CLAUDE.md, capability content, and settings.json

`CLAUDE.md` is per-project — it carries `# capability: X` sections matching *your* config,
which the template's does not. Do **not** overwrite it. Two kinds of content need attention:

**Always-on prose — hand-apply.** Compare and apply new always-on principles into your
`CLAUDE.md`; leave your `# capability:` sections for the next command to handle.

```bash
git show framework/main:CLAUDE.md
```

**Capability content — run `resync` (do not hand-edit).** The capability sections in
CLAUDE.md and the `# capability:` blocks in your role files are spliced from the framework
snippets you just pulled (`claude-snippets/`, `capabilities.md`). When that source content
changes upstream, your spliced copies go stale — this is easy to miss, because the blocks are
still present, just outdated. Refresh them from the current snippets:

```bash
python _framework/tools/framework.py --dry-run resync   # preview (--dry-run is a global flag: it goes before the subcommand)
python _framework/tools/framework.py resync             # apply
```

`resync` re-splices the marker-delimited blocks in place for every *enabled* capability. It
touches nothing else — no file creation, no config changes, no effect on always-on prose — so
it is safe to run on every upgrade. (Before this command existed, stale capability guidance
survived upgrades silently; if your project predates it, one disable/enable round-trip per
capability is the manual equivalent.)

If the template's `.claude/settings.json` (hook wiring) changed, reconcile it by hand too,
rather than overwriting, in case you customized it.

### Step 5: Run migrations newer than your framework_version

Read `framework_version` from `_framework/config.yml`. If it is absent, treat the project as
the oldest and apply all of the below. Each migration is idempotent/conditional; apply those
whose release is newer than your version.

**Release 2026-08-14**

- **Exchange field rename.** In `exchanges/**/*.md`, rename `asker_area`→`from_area`,
  `asker_role`→`from_role`, `responder_area`→`to_area`, and add `kind: query`. Skip if
  there is no `exchanges/` directory or the files already use `from_area`.
- **Frontmatter wikilink repair.** Any commons page promoted under the old tool has
  corrupted nested-list frontmatter (`evidence:` followed by `- - - path`). Restore each to
  a quoted wikilink (`- "[[path]]"`). Lint Rule 2 flags these, so Step 7 points you at the
  exact pages.
- **Post-bootstrap cleanup.** Remove any template/author-only files a pre-cleanup bootstrap
  left behind (none in the normal case): `rm -f SETUP.md UPGRADING.md
  _framework/future-work.md _framework/maintaining.md`. If your top-level `README.md` still
  describes the *framework* rather than your project, replace it.
- **Un-supersede promoted sources.** If any area page was marked `superseded` pointing at a
  commons copy (the old, incorrect `/promote` advice), revert it — promotion coexists, it
  does not replace, and a superseded page with live inbound citations is a lint error.

**Release 2026-08-15**

- **Commons drift & link management (5c/5d) — twin-edge backfill.** This release adds the
  twin edge between a commons page and its source: `promoted_from_page` + `aligned_on` on the
  commons page, and a `commons_twin: "[[…]]"` back-pointer on the source area page. Pages
  promoted *before* this release lack all three. New promotions get the edge automatically;
  pre-existing pages need a one-time backfill if you want drift detection to work — **without
  `aligned_on`, Rule 20 cannot drift-check the page.** To find exactly which pages need it,
  enable the rule and run lint: `/framework enable-lint rule_20_commons_drift` then
  `python _framework/tools/lint.py` — every un-checkable commons page is reported by name (it
  no longer silently passes). For each: on the commons page add `promoted_from_page` (its
  source id) and `aligned_on` (today), and add `commons_twin: "[[<commons-id>]]"` to the
  matching source page. Re-run lint until only genuine drift (or nothing) remains. Skip if you
  have no `commons/kb/` pages.
- **Remove forked `…-commons-commons-…` pages.** A pre-fix `/promote` run on an id that was
  already a commons id silently forked a second page with a doubled prefix (e.g.
  `f-commons-commons-lens-fit-recipe`). The fixed tool refuses this, but any existing fork
  stays on disk. Search `commons/kb/` for ids containing `-commons-commons-`; if found, merge
  its content back into the real commons page and delete the fork. Rule 18 won't catch these
  (the forked id is itself unique). Skip if none exist.
- **`enable-lint` now recognizes the shipped warning rules.** `/framework enable-lint` /
  `disable-lint` derive their accepted set from the shipped rule modules, so
  `rule_20_commons_drift` and `rule_21_commons_twin_links` now work (previously they errored
  as "unknown" while the rules themselves were live). Code-only — arrives on pull. Optional
  tidy-up: your project's `_framework/config.yml` may still list the eight planned-but-
  unimplemented `warnings_visible` keys (`rule_4_orphans`, `rule_8_…`, etc.); they are inert
  and may be removed, leaving only the rules you actually run.
- **No action needed:** the commons-id idempotence fix, the `/promote` commons-id rejection,
  and the `→ to be filed:` path normalization are code-only — they take effect the moment you
  pull the framework in Step 4.

**Release 2026-08-16**

- **Rule 20 no longer skips un-checkable commons pages silently.** Previously a commons page
  missing `aligned_on`/`promoted_from_page` was skipped without a word, so an enabled rule
  could report `lint: clean` while covering zero pages (a false negative). It now reports each
  such page by name. Code-only — arrives on pull. This is the discovery tool for the
  2026-08-15 twin-edge backfill above: enable the rule, run lint, and fix the pages it names.
- **New `/framework resync` — refreshes stale capability content.** Capability sections in
  `CLAUDE.md` and `# capability:` blocks in role files are spliced from framework snippets;
  when the snippet content changed upstream, older upgrades left the spliced copies stale
  (Step 4 used to say "leave capability sections intact"). Step 4 now runs `resync` to
  re-splice them from the current snippets — run it once as part of this upgrade to pick up
  any capability guidance that changed since your last one (e.g. the cross-area read stance in
  `multi_area`). Non-destructive; content-only.
- **Role files: reference the baseline skill set instead of enumerating it.** Implementer role
  files used to hardcode the always-available skill list in their `## Allowed skills` section,
  so a newly-shipped baseline skill (e.g. `amend-commons`) never reached existing roles — the
  role forbade a skill the framework ships and `/promote`'s own error points you to. The
  baseline now lives once in `_framework/schema/capabilities.md` → "Always-available skills",
  and roles reference it. Migrate each **implementer** role file (`areas/*/roles/*/role.md`,
  not `*-reviewer` or the coordinator): in its `## Allowed skills` section, replace the
  enumerated baseline line (the `start, ingest, ask, …` line *outside* any `# capability:`
  block) with: *"All always-available skills — see `_framework/schema/capabilities.md` →
  'Always-available skills'."* Leave the `# capability:` blocks alone (resync owns those).
  Leave coordinator and `*-reviewer` roles' skill lists as-is — those are deliberate
  restrictions, not the baseline. After this, a new baseline skill reaches every role for
  free.

**Release 2026-08-17**

- **`/promote` now files its "Awaiting your ack" INBOX entry.** `promotion-protocol.md` step 7
  always specified it, but `promote.py` never wrote it and the skill stopped at "brief the
  user" — so a promoted page could sit unreviewed with no INBOX signal. `promote.py` now
  appends the entry under `## Awaiting your ack` in `INBOX.md`. Code-only — arrives on pull; no
  action needed. (If your `INBOX.md` lacks that section header, the tool warns and skips it
  rather than failing — add the header to receive the entries.)

**Release 2026-08-22**

- **`/wrap-up` warns on out-of-order `pulse.log` entries.** `pulse_compact.py` now checks that
  entry timestamps are non-decreasing top-to-bottom and warns if one is earlier than the entry
  above it — the usual sign an agent prepended instead of appending. Code-only — arrives on
  pull; no action needed.
- **Rule 10 (promotion freshness) is now implemented.** `promotion-protocol.md` documented it
  as the backstop for unreviewed promotions, but no rule module existed and
  `promotion_freshness_active_days` was an orphaned config key. It's now a self-gating warning
  that flags commons pages still `human_reviewed: false` past the threshold. Code arrives on
  pull; it's **off by default** — enable with `python _framework/tools/framework.py enable-lint
  rule_10_promotion_freshness` (or `/framework enable-lint …`) if you want the backstop. If
  your project has old promotions never acked, enabling it will surface them; review and set
  `human_reviewed: true` (or leave it off).

**Release 2026-08-23**

- **Task status uses the `_Status:_` vocabulary, not checkboxes — convert existing `tasks.md`.**
  Five skills (`plan`, `implement`, `replan`, `wrap-up`, `review`) had drifted to a `- [ ]` /
  `- [x]` checkbox convention that the task template and Rule 11 never used. The skills now
  track status on the template's `_Status:_` line (`planned | in_progress | done | blocked |
  superseded`). This matters because a checkbox has two states and can't express
  `blocked`/`superseded`, and `/wrap-up`'s "spec complete" gate was silently unsatisfiable
  against `_Status:_`-form files. **Migration:** in any `tasks.md` that uses checkboxes,
  convert each task to the template shape — `- [x]` → `_Status:_ done`, `- [ ]` → `_Status:_
  planned` (or `in_progress`/`blocked` as appropriate), and add the `_Boundary:_`/`_Depends:_`/
  `_Owner role:_` lines if missing (see `_framework/schema/spec-template/tasks.md.tmpl`). Skip
  if your `tasks.md` files are already in template form (many are — the template itself carried
  no checkbox, so specs authored from it are already correct). Code/skills arrive on pull; only
  the `tasks.md` conversion is manual.

**Release 2026-08-25**

- **`areas-index.md` heading levels fixed (Rule 15).** Top-level areas were rendered as `####`
  (h4) under the `##` commons heading, skipping h3, due to an off-by-one in the index
  generator. Now `###` for a top-level area, `####` for a sub-area. Code-only — the next lint
  run regenerates `areas-index.md` with corrected levels; no manual action.
- **Dangling references to template-only files removed.** `spec.md` and `lint-rules.md`
  referenced `future-work.md`/`maintaining.md` by local path — files deleted at bootstrap, so
  the links dangled in every live project. Rephrased to self-contained wording. Doc-only —
  arrives on pull.
- **New `framework_check.py` — hard-edge self-consistency checks.** Verifies config
  `warnings_visible` == the shipped warning rules, no pulled doc references a maintainer-only
  file, and `framework_version` == the latest release. Maintainer/CI tool (run
  `python _framework/tools/framework_check.py`); no effect on a running project — it degrades
  gracefully when its inputs (e.g. `UPGRADING.md`) are absent. Code-only — arrives on pull.

**Release 2026-08-26**

- **Session state file (`_session.json`) — foundation for `/kb-vitals`.** New
  `session_state.py` + wiring records the adopted role/area, session id, transcript path, and
  session-start time in a git-ignored `_session.json` at the repo root: `/start` writes it,
  the session-start hook resets/stamps it on a new session, and (soon) `/kb-vitals` reads it.
  Code arrives on pull. **One manual step:** `.gitignore` is not pulled, so add `/_session.json`
  to your project's `.gitignore` (it holds per-session, per-machine runtime state and must not
  be committed). No other action — nothing reads the file yet except `session_state.py show`.
- **New `/kb-vitals` skill — operational state + next actions.** `kb_vitals.py` scans human
  vitals (INBOX "Needs decision", commons pages awaiting review, proposals ready to promote —
  project-wide) and role vitals (wrap-up due, pulse over-cap, blocked/complete specs, a
  restart nudge when the live session context passes `kb_vitals.context_restart_threshold_tokens`
  or a preloaded page changed since you adopted). Reads `_session.json`; runs no lint. Always-
  available skill — code/skill arrive on pull. Optional: set `kb_vitals.context_restart_threshold_tokens`
  in your `config.yml` (default 400000; tune to your context window).
- **New status line — at-a-glance vitals.** `statusline.py` + `statusline.sh` render
  `<project> · <role@area> · <⚠N pending | ✓> · ctx <N>k[!]` (`!` = context past the restart
  threshold). Cheap per render (tail-reads the transcript; no KB scan). Code arrives on pull.
  **One manual step:** `.claude/settings.json` is reconciled by hand (Step 4), so add the
  `statusLine` block to yours:
  `"statusLine": { "type": "command", "command": "bash $CLAUDE_PROJECT_DIR/_framework/hooks/statusline.sh" }`.
  Like the hooks, it activates on the next launch after the setting is present.
- **Fix: context size no longer read from the wrong session.** The context-token fallback
  munged the repo root to locate the transcript, but Claude Code keys it on the session cwd —
  so when they differ (launched from a parent dir, or the hook-less install session) it read a
  *foreign* session's context and showed it as authoritative. It now reconstructs the exact
  path from session identity (cwd + session_id) or returns nothing — never guesses. Code-only,
  arrives on pull; the status line and `/kb-vitals` simply show no `ctx` figure until an
  authoritative source exists (hook-recorded transcript, or the status-line payload).

**Release 2026-08-27**

- **Fix: session state is now per-session (`_session/<session-id>.json`).** The single repo-global
  `_session.json` was a shared write target: two Claude Code sessions in one repo (say a
  researcher and a reviewer) overwrote each other's role/area/transcript, so `/kb-vitals` and the
  status line silently reported the *other* session's state. State is now sharded one file per
  session under `_session/`, keyed on the Claude session id (`$CLAUDE_CODE_SESSION_ID` for agent
  tools, the `session_id` payload field for hooks and the status line). Files from sessions that
  ended without the end hook are swept at session start (7 days). Code arrives on pull.
  **One manual step:** `.gitignore` is not pulled — change the `/_session.json` line you added in
  Release 2026-08-26 to `/_session/` (or add `/_session/` if you skipped it), then delete the
  now-orphaned `_session.json` at your repo root; it is unread and harmless, but dead. Nothing
  else to do: the next session-start hook writes the new file, and `/start` overwrites it.
- **Status line: H / R indicators, colored, with a `/kb-vitals` prompt.** The single
  `⚠N | ✓` counter (INBOX items only) is replaced by two: **H** — what you owe project-wide
  (INBOX "Needs decision" and "Awaiting your ack", proposals ready to promote, commons pages
  awaiting review) — and **R** — the adopted role's hygiene (uncompacted pulse.log, pulse.md
  over cap, blocked tasks, finished specs with no outcome.md, stale preload, open exchanges),
  shown as `–` when no role is adopted. Green = clear, yellow = hygiene, red = blocking (a
  decision you owe, or a blocked task); `run /kb-vitals` is appended when anything is pending.
  Code arrives on pull. Optional: `statusline.color: false` in your `config.yml` if your
  terminal renders escape codes literally (the `NO_COLOR` environment variable also works).
- **New vitals cache — `_framework/telemetry/vitals-cache.json`.** Three of the vitals need a
  frontmatter walk of the whole KB (~74ms, unbounded as the KB grows), which the status line
  cannot pay for on every render. They are now snapshotted to a cache that `/kb-vitals`,
  `lint.py` (so `/check` and `/wrap-up`), and `/start` + the session-start hook refresh —
  bounding staleness to a single session, which is well inside the tolerance of counts that
  move on the order of days. Everything fast-moving is still computed live per render.
  `/kb-vitals` itself never reads the cache: it stays authoritative. The file lives in the
  already-git-ignored telemetry directory, so there is no `.gitignore` change and nothing to
  do — it is rebuilt on the next session start, `/check`, or `/kb-vitals`.

Set `framework_version` in `_framework/config.yml` to the version of the template you just
pulled (the template's `_framework/config.yml` carries the current value).

### Step 7: Verify with lint

```bash
python _framework/tools/lint.py
```

Optionally, also run the tool test suite — this is the step that needs the dev extra:

```bash
pip install -r _framework/tools/requirements-dev.txt
python -m pytest _framework/tools/tests/ -q
```

The updated rules are your migration checker — Rule 2 surfaces remaining frontmatter
corruption or broken links; Rule 18 catches id collisions. Fix what it flags and re-run
until clean.

### Step 8: Commit (and how to roll back)

Commit the upgrade branch and review the full diff before merging. If anything looks wrong,
roll back cleanly — nothing was touched outside the branch:

```bash
git checkout <your-default-branch> && git branch -D framework-upgrade
```

Once satisfied, merge the branch.

**Release 2026-08-29**

- **Fix: `/kb-vitals` and the status line never reported exchanges.** With `multi_area` on, the
  exchange scan was dead code — it returned zero unconditionally, so a role was never told it had
  an open query to answer, an answered query to close, or a brief to dispose of, and the status
  line's **R** indicator stayed clean. Two independent defects each suppressed it on their own:
  the scan globbed `q-*.md` (nothing `/exchange` writes is named that — the id is
  `ex-<date>-<slug>`), and it compared the repo-relative area it was passed (`areas/research`)
  against the bare area name exchange frontmatter carries (`research`). A third defect would have
  misrouted the result: briefs were counted with queries and pointed at `/respond-exchange`, which
  does not apply to them — a brief has no responder, and only the roles still in its `open_for`
  owe it a disposition. All three are fixed, queries and briefs now report separately with the
  right command, and briefs are counted per-role. **Code-only; takes effect on pull in Step 4.**
  The status line's cache gains a per-role `briefs_open` key, written on the next refresh
  (`/kb-vitals`, `/check`, `/wrap-up`, or session start) — no action needed.
  Worth knowing: `/start` step 5 tells the agent to scan `exchanges/*/` by hand, which masked this
  at session start — but it only fires *at* session start. An exchange answered by another area
  while your session is already running had nothing to surface it. If you have been running with
  `multi_area` on, check `exchanges/*/` for answered queries your area filed and never closed;
  `/kb-vitals` will list them from now on.
- **`/wrap-up` clarifies that it does not un-adopt the role.** Doc-only. Wrap-up closes a working
  session in the bookkeeping sense but never touches `_session/<session-id>.json`, so the role,
  area and preload survive it — an agent read the two skills together and concluded it had to
  re-`/start` before continuing, which was never required. The skill now says so, and says that
  `/start` is needed only for a role *change* or after a `/clear`. **No action; takes effect on
  pull in Step 4.**

**Release 2026-08-30**

- **Lint now checks spec files' wikilinks (Rules 2 and 5). Expect new errors on your first
  `/check` — fix them as part of the upgrade.** `/plan`, `/replan` and the brief template all
  tell agents to cite kb pages by wikilink from a `brief.md`, `plan.md`, `tasks.md`,
  `revisions.md` or `outcome.md`, but no rule ever read those files, so the citations could rot
  silently — a page renamed or promoted left dangling links in every spec that cited it, with
  nothing to say so. Rule 2 (unresolvable link, wrong `area:` prefix) and Rule 5 (link to a
  superseded page) now walk spec files on the same terms as kb pages. Specs remain exempt from
  *frontmatter* requirements — Rule 1 still checks well-formedness only.
  **Action:** run `python _framework/tools/lint.py` right after upgrading and fix what it
  reports in `*/specs/*`. These are real broken links that were already there; the rule only
  made them visible. Note `/wrap-up` will not complete while lint is dirty, so do this before
  your next wrap-up rather than during one.
- **`revisions.md` is now linted at all.** It was missing from the spec-file set entirely, even
  though `/replan` tells agents to cite kb pages in it. It is now covered by Rules 1, 2 and 5
  like its siblings. Same action as above.
- **Rule 5 now catches area-prefixed links to superseded pages.** The status index is keyed on
  bare ids, but the rule looked up the raw link text, so any `[[research:findings/f-…]]` form
  slipped past — cross-area citations of a retired page were never flagged. Fixed by stripping
  the prefix before lookup. This applies to kb pages too, so it may surface findings unrelated
  to specs. Same action.
- **`/plan` corrected: link a prior spec's `outcome.md` as a relative markdown link, not a
  wikilink.** `link-conventions.md` is normative — references to files outside `kb/` use
  relative markdown links — and an `outcome.md` wikilink could never have resolved, since the
  wikilink index only holds kb pages. If you have plans citing `[[…outcome]]`, rewrite them as
  `[name](../<spec>/outcome.md)`; Rule 2 will now flag them.
- **Brief template: the `## Pointers` placeholders are no longer live wikilinks.** They shipped
  as `[[concepts/...]]` / `[[findings/...]]`, which under the new rule would make every unfilled
  brief an error. They are now plain angle-bracket placeholders. Existing briefs that still
  carry the old placeholders will be flagged — replace them with real citations or delete the
  line. Code and template arrive on pull.

**Release 2026-08-31**

- **Lint now resolves relative markdown links (Rule 2). Expect more new errors on your first
  `/check`.** `lint-rules.md` has claimed since the rule was written that "every relative
  markdown link to a repo path resolves to an existing file" — no code ever did it. So the
  non-wikilink half of the link story was unenforced: `link-conventions.md` directs every
  reference to a file *outside* `kb/` (code, manifests, raw materials, another spec's
  `outcome.md`) to be a relative markdown link, and none of them were resolved. This lands
  together with yesterday's spec-file coverage and matters more because of it — Release
  2026-08-30 moved `/plan`'s spec-to-spec citations from wikilinks into exactly this form.
  A leading `/` reads as repo-root-relative, and a link resolving outside the repository is an
  error. Skipped as not-repo-paths: URL schemes (`https:`, `mailto:`, …), protocol-relative
  `//`, bare `#anchor` targets, and angle-bracket placeholders like `../<spec>/outcome.md`.
  Fenced code blocks and inline code spans are skipped too, so a page documenting link syntax
  is not flagged for its own examples.
  **Action:** same as the previous release — run `python _framework/tools/lint.py` and fix what
  it reports, outside a `/wrap-up`. Findings carry a line number. If you upgrade past both
  releases at once, do the two together; they surface the same class of pre-existing breakage.

**Release 2026-09-01**

- **Backfill missed since Release 2026-08-15: commons pages promoted before the curation
  requirement.** That release added a content requirement to `promotion-protocol.md` step 4 —
  a commons page is edited *for a commons reader*: strip resolved-deliberation cruft (resolved
  question sections, superseded sections, closed "left open" lists). The link half of that same
  step got a migration and a lint rule (Rule 21); **the prose half shipped with neither**, so
  pages promoted earlier were never brought into compliance and nothing has surfaced them
  since. Rule 20 sees no drift (their `aligned_on` isn't older than any source `updated`) and
  Rule 21 is clean, so `lint: clean` has been asserting nothing at all about step-4 compliance.
  **Action (one-time, manual — lint cannot judge prose, but it can name the candidates):**

  ```bash
  grep -rl "^promoted_on:" commons/kb --include='*.md' | while read -r f; do
    d=$(sed -n 's/^promoted_on: *//p' "$f" | head -1)
    if [ -n "$d" ] && [ "$(printf '%s\n' "$d" "2026-08-15" | sort | head -1)" = "$d" ] \
       && [ "$d" != "2026-08-15" ]; then echo "$f  ($d)"; fi
  done
  ```

  That prints every commons page promoted before the requirement existed — your worklist. Read
  each one as a newcomer would and remove deliberation that only made sense in its source area.
  Leave `aligned_on` alone — you are editing the commons copy to match a requirement, not
  reconciling it with its source, and touching it would suppress a real drift signal. Log the
  edits in `commons/CHANGELOG.md` as `/amend-commons` would.

- **Data manifests: the type convention is now written down.** A manifest under
  `data/manifests/` is `type: source` with an `s-` id prefix and
  `provenance.kind: internal-experiment` — there is no `manifest` type, and Rule 1 checks
  manifests in full, so filing one as `type: manifest` with an `m-` id fails twice with no
  document explaining why. This was always what the tooling enforced; only the documentation
  was missing (`frontmatter.md` → "Data manifests"). **Action:** if you filed a manifest under
  a different type to satisfy lint, nothing needs changing — but note the convention. If you
  have a manifest that never passed lint, `type: source` + `s-<date>-<slug>` is the fix.

- **Rule 2 now resolves manifests' `context_pages`.** Rule 12 requires that list be "non-empty
  wikilinks into `kb/`" and only ever checked non-emptiness, so a manifest could cite pages
  that don't exist. Those links are now resolved like any other frontmatter wikilink. Also
  worth knowing: manifests live outside `kb/` and are **not** in the wikilink index, so a
  `[[data/manifests/…]]` reference from a kb page can never resolve — link a manifest with a
  relative markdown link, which Release 2026-08-31 made checkable. **Action:** run
  `python _framework/tools/lint.py`; fix any manifest links it reports.

---

## Notes for the agent

- Only framework machinery is replaced; project knowledge (`commons/`, `areas/`,
  `exchanges/`) is never overwritten.
- `_framework/config.yml` is never pulled — it holds your capability flags and
  `framework_version`.
- If a migration doesn't apply to your project (e.g. no exchanges), skip it silently.
- When unsure about a framework file's role, the pulled `_framework/spec.md` §2 is the
  canonical project layout.
