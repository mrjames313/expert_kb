---
name: replan
description: Revise an in-progress spec when assumptions change, a blocker appears, or the goal shifts. Updates plan.md and tasks.md while preserving history.
---

# /replan

Updates an existing `plan.md` and `tasks.md` in response to changed circumstances. Preserves the audit trail rather than rewriting silently.

## When to use

- A concept the plan depended on was falsified.
- A blocker emerged that wasn't anticipated.
- The user's goal shifted while work was in flight.
- A `/wrap-up` from a prior session surfaced something that invalidates remaining tasks.

If the existing plan is mostly fine and only one task needs to change, just edit `tasks.md` directly inside `/implement`. `/replan` is for changes that touch the plan's approach or multiple tasks.

## Steps

1. **Read the current spec.** Read `brief.md`, `plan.md`, and `tasks.md` for the spec being revised. Note each task's `_Status:_` (`done` / `in_progress` / `planned` / `blocked`) to see what's finished, in flight, and unstarted.

2. **Discuss with the user.** Explicitly: what changed, and what does the user want to do about it? Don't replan unilaterally — confirm the new direction. If the user is reacting to something you discovered, lay out the discovery and 2–3 options for how to proceed.

3. **Update `plan.md`.** Don't rewrite it. Append a new section at the bottom:
   ```markdown
   ## Revision YYYY-MM-DD

   **Trigger:** What prompted this revision. Cite any kb pages with `[[wikilinks]]`.

   **Change:** What's different now (e.g., "Approach now sequences X before Y because Z").

   **Carried forward:** Which parts of the original plan still hold.
   ```
   Leave the original approach/milestones text intact above. The history matters.

4. **Update `tasks.md`.** For each task:
   - Done tasks stay done (`_Status:_ done`). Don't touch them.
   - Unstarted tasks that are no longer needed: set `_Status:_ superseded` and note the reason in a trailing comment. Don't delete them — the record of what was dropped and why is the point.
   - Unstarted tasks that still apply: leave as-is, or edit if the revision changes their scope.
   - New tasks: append new `### T<n>:` blocks (template shape) with the revision date in a comment. Preserve every task's `_Boundary:_`/`_Depends:_`/`_Owner role:_` annotations — don't flatten tasks into bare bullets.

   Example:
   ```markdown
   ### T1: Original task 1
   _Boundary:_ /areas/research/kb/**
   _Depends:_ —
   _Status:_ done
   _Owner role:_ researcher

   ### T3: Original task 3
   _Boundary:_ /areas/research/kb/**
   _Depends:_ —
   _Status:_ superseded   <!-- 2026-05-15: concept c-... was falsified -->
   _Owner role:_ researcher

   <!-- added 2026-05-15 revision -->
   ### T5: New task reflecting the revised approach
   _Boundary:_ /areas/research/kb/**
   _Depends:_ T4
   _Status:_ planned
   _Owner role:_ researcher
   ```

5. **Record in pulse.log.** Append a `decision` event:
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Replanned <spec-name>: <one-line summary of the change>.
   → to be filed: decisions/d-YYYY-MM-DD-replan-<spec-name>
   ```
   Then create the corresponding `decision` page under `areas/<area>/kb/decisions/` documenting the rationale (including alternatives considered).

6. **Verify.** Run `python _framework/tools/lint.py`. Fix any new errors.

7. **Brief the user.** Summarize what changed in the plan and what task to do next.

## Notes

- The history-preserving format is intentional. Specs are not just current state — they're a record of how the work evolved. Squashing history makes it impossible to learn from past course corrections.
- A `/replan` always produces a `decision` page. The rationale ("why we changed direction") is one of the most valuable things to preserve.
- If a `/replan` would mean abandoning more than half the tasks, consider whether you really want a new spec instead. Talk to the user.
- If `por` is enabled, also update `POR.md` for the area (and `commons/POR.md` if the change has cross-area implications). The coordinator role (if present) is responsible for the commons POR; otherwise update it yourself.
- Don't `/replan` to fix a mistake you just made in `/implement`. Just revert the bad work and continue. `/replan` is for *external* circumstances changing, not for self-correction.
