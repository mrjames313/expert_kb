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

---

## Notes for the agent

- Only framework machinery is replaced; project knowledge (`commons/`, `areas/`,
  `exchanges/`) is never overwritten.
- `_framework/config.yml` is never pulled — it holds your capability flags and
  `framework_version`.
- If a migration doesn't apply to your project (e.g. no exchanges), skip it silently.
- When unsure about a framework file's role, the pulled `_framework/spec.md` §2 is the
  canonical project layout.
