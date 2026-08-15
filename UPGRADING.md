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
not part of a live project and this pull does not add them. In the normal case none are
present. Only if a *pre-cleanup* bootstrap left stale copies behind, remove them once you've
finished following the fetched instructions: `rm -f SETUP.md UPGRADING.md
_framework/future-work.md _framework/maintaining.md`.

Review before continuing: `git diff --staged`.

### Step 4: Reconcile CLAUDE.md (and settings.json) by hand

`CLAUDE.md` is per-project — it carries `# capability: X` sections matching *your* config,
which the template's does not. Do **not** overwrite it. Compare and hand-apply only the
always-on additions:

```bash
git show framework/main:CLAUDE.md
```

Apply new always-on principles into your `CLAUDE.md`; leave your capability sections intact.
If the template's `.claude/settings.json` (hook wiring) changed, reconcile it the same way
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
- **Post-bootstrap cleanup.** Remove template-only files if present (see Step 3). If your
  top-level `README.md` still describes the *framework* rather than your project, replace it.
- **Un-supersede promoted sources.** If any area page was marked `superseded` pointing at a
  commons copy (the old, incorrect `/promote` advice), revert it — promotion coexists, it
  does not replace, and a superseded page with live inbound citations is a lint error.

### Step 6: Bump framework_version

Set `framework_version` in `_framework/config.yml` to the version of the template you just
pulled (the template's `_framework/config.yml` carries the current value).

### Step 7: Verify with lint

```bash
python _framework/tools/lint.py
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
