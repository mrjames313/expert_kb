---
name: implement
description: Execute one task from a spec. Reads the task, does the work, writes any new kb pages (findings, decisions, concepts), and appends events to pulse.log. Use for one task at a time.
---

# /implement

Executes one task from `tasks.md` end-to-end: reads the task, does the work, writes any kb pages it produced, and journals what happened.

## When to use

- A spec exists at `areas/<area>/specs/<name>/` with `tasks.md` populated.
- The user (or you) has picked one task to do next.

If `tasks.md` doesn't exist, run `/plan` first. If the task implicates other areas, escalate (see Notes).

## Steps

1. **Identify the task.** Either the user named it (e.g. "/implement task 3"), or you pick the next unchecked one. Read its description and any dependencies it lists.

2. **Confirm scope.** Re-read the task's referenced kb pages and any related findings/concepts under test. If the task as written doesn't make sense given the kb, stop and ask the user (don't silently expand the task).

3. **Do the work.** Make whatever edits the task requires:
   - **Code changes** — edit files under `areas/<area>/code/`.
   - **Data manifests** — write to `areas/<area>/data/manifests/`.
   - **New kb pages** — write to `areas/<area>/kb/{findings,decisions,concepts}/`. Use the type templates in `_framework/schema/`. Consider whether the page warrants a `when_to_load` field — fill it in only when there's a useful "don't load" signal (e.g., the page has a cheaper alternative for the common case, or its scope might not be obvious from `summary` + `relevant_to`). Skip the field otherwise; missing is fine.

   Stay within the role's write boundaries (see the role file's "Operating boundaries" section). Never modify `raw/` files — they're immutable. Never modify pages outside your area unless `multi_area` is enabled and you're using `/exchange`.

4. **For each new finding, decision, or concept page**, journal it in `_journal/pulse.log`:
   ```
   ## [YYYY-MM-DD HH:MM] finding <role>
   Brief 1–2 line summary of the finding.
   → to be filed: findings/f-YYYY-MM-DD-<slug>
   ```
   Use the appropriate event type: `decision`, `finding`, `concept`. For mid-task realizations that change focus, use `focus-shift`. For open questions surfaced during work, use `question`. If a `decision` or `finding` you just produced resolves an open question that was already in `pulse.md`, also append a `question-closed` entry with a `→ closes:` directive — don't wait for `/wrap-up` to find it:
   ```
   ## [YYYY-MM-DD HH:MM] question-closed <role>
   Confirmed Rule 152 does not apply — see [[d-...]].
   → closes: Does Rule 152 apply here?
   ```

5. **Mark the task done.** In `tasks.md`, set the task's `_Status:_` line to `done` (or `blocked` if it can't proceed, noting why in Implementation Notes). Set it to `in_progress` when you pick the task up.

6. **Verify.** Run `python _framework/tools/lint.py`. Fix any errors before stopping. Common ones:
   - Missing required frontmatter fields (Rule 1).
   - Wikilinks pointing at non-existent pages (Rule 2).
   - Concept at `under_test` status without `evidence` (Rule 6).

   If lint isn't clean after your fixes, surface remaining issues to the user.

## Notes

- **One task at a time.** Don't chain multiple tasks in one invocation. Each `/implement` is one task, journaled, lint-clean. The user decides whether to continue with the next one.
- **When `task_subagents` is enabled**, this skill runs in a fresh subagent (the orchestrator spawns it). The subagent gets the spec context but starts with empty conversational state. It returns the diff + journal entries to the orchestrator.
- **When `formal_review` is enabled**, after a task is implemented, the orchestrator may invoke `/review` on the same task via a reviewer subagent. Don't run `/review` yourself from inside `/implement`.
- **Mid-task realizations.** If during work you realize the task's assumptions are wrong (e.g. a concept it depends on was just falsified), stop. Journal a `focus-shift` event, and tell the user. They'll likely want `/replan`.
- **Don't write `outcome.md` here.** The outcome page summarizes a finished *spec*, not a finished *task*. It's written by `/wrap-up`.
- **Don't modify pulse.md directly.** Only append to `_journal/pulse.log`. `/wrap-up` compacts the log into pulse.md.
- If a task is ambiguous or under-specified, ask the user once. If they say "you decide", journal your decision explicitly as a `decision` event so the rationale is preserved.
