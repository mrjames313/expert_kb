---
name: framework
description: Manage framework capabilities (multi_area, por, task_subagents, formal_review), control lint warning visibility, prune stale role preload entries, and pull framework updates. Wraps framework.py (except `update`, which fetches the latest UPGRADING.md).
---

# /framework

A pass-through to `_framework/tools/framework.py` for capability and lint-visibility management. The skill's job is to show plans before applying, confirm changes that affect many files, and verify the project remains healthy afterward.

## When to use

- User wants to enable or disable a capability (`/framework enable por`, `/framework disable multi_area`).
- User wants to surface a configurable lint warning (`/framework enable-lint rule_8_stale_concept`) or stop showing one.
- User wants to see current state (`/framework status` or just `/framework`).
- User wants to clean up stale preload entries (`/framework prune`).
- User wants to pull the latest framework into this project (`/framework update`).

## Steps

1. **Parse the user's intent.** The subcommands mirror `framework.py`:
   - No args, or `status` → show capability + lint visibility status.
   - `enable <capability>` / `disable <capability>` → toggle a capability.
   - `enable-lint <rule>` / `disable-lint <rule>` → toggle a lint warning's visibility.
   - `lint-status` → just the lint visibility portion of status.
   - `prune [<role>]` → list (or apply, with `--apply`) stale preload entries.
   - `update` → pull the latest framework into this project (not a `framework.py` command — see the update step below).

2. **For status queries** — just run the command and show the user:
   ```
   python _framework/tools/framework.py status
   ```

3. **For capability enable/disable** — show the plan first:
   ```
   python _framework/tools/framework.py --dry-run enable <capability>
   ```
   Walk the user through what will change: which files get edited (CLAUDE.md, role files), which get created (POR.md files for `por`, reviewer roles for `formal_review`), any warnings (e.g., disabling `por` leaves POR.md files inert on disk).

   If the user confirms, apply:
   ```
   python _framework/tools/framework.py enable <capability>
   ```

   Then verify:
   ```
   python _framework/tools/lint.py
   ```

4. **For lint visibility toggles** — these are config-only changes (no file edits), so the plan is short. Just apply:
   ```
   python _framework/tools/framework.py enable-lint <rule>
   ```
   Tell the user the rule is now visible; subsequent `/check` invocations will surface findings from it.

5. **For prune** — first list:
   ```
   python _framework/tools/framework.py prune
   ```
   Or narrow to one role:
   ```
   python _framework/tools/framework.py prune <role-name>
   ```

   The output groups candidates by role with a reason for each. For lifecycle-flagged entries (target page is superseded/falsified/dropped), removal is safe. For activity-flagged entries (not cited in N sessions), confirm with the user — these are heuristics, and a low-activity preload may still be doing useful orientation work (`/CLAUDE.md` is preloaded but rarely *cited*).

   If the user approves the candidates (or a subset), apply:
   ```
   python _framework/tools/framework.py prune --apply
   ```
   (Or with a role filter to apply just one role's candidates.)

6. **For `update`** — this is *not* a `framework.py` call. Pull the latest framework by fetching and following the canonical upgrade runbook, so the procedure stays current even if this skill is itself outdated:
   ```
   git remote add framework https://github.com/mrjames313/expert_kb.git 2>/dev/null || true
   git fetch framework
   git show framework/main:UPGRADING.md
   ```
   Read that file and follow it exactly — it handles the clean-committed-tree safety gate (so the upgrade is reversible), pulling framework files (not project content), reconciling CLAUDE.md, running version-keyed migrations, and lint verification. Don't substitute these local steps for the fetched instructions.

7. **Brief the user.** Summarize what changed. For capability changes, point at the relevant `_framework/schema/capabilities.md` section so they can read about the new behavior.

## Notes

- **Dependencies are surfaced automatically.** `enable formal_review` without `task_subagents` returns an error explaining which capability needs to be enabled first. `disable task_subagents` while `formal_review` is on is similarly blocked.
- **Disable doesn't delete data.** Disabling `por` removes the coordinator role and POR preload entries from role files, but `POR.md` files themselves stay on disk (they become inert; re-enabling picks them up again). Tell the user this when they disable `por` so they know nothing's lost.
- **Prune respects capability blocks.** Entries inside `# capability: X` markers in role files are managed by the capability system, not by prune. Prune flags them for visibility but `--apply` skips them. The user must `/framework disable X` if they want those entries gone.
- **Lint visibility toggles take effect immediately.** No need to restart anything; the next `/check` reads the updated config.
- For a full reference of subcommands, flags, and exit codes, see `_framework/tools/README.md`.
