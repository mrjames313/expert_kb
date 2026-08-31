---
name: wrap-up
description: Close out a working session. Compacts pulse.log into pulse.md, writes outcome.md for any completed specs, runs lint, and records a session_end telemetry event with citation/load metadata.
---

# /wrap-up

Closes a working session cleanly: compacts the journal into pulse.md, finalizes any completed specs, verifies lint, and records the session_end event.

## When to use

- End of a working session (always).
- Before switching roles — the full sequence is `/wrap-up`, then `/clear`, then `/start <other-role>`. The `/clear` is the step that actually drops the old role's context, and the one that gets skipped.
- Before committing work to git.
- If the user is stopping for the day and won't return for a while.

If a session ends without `/wrap-up`, pulse.log will be non-empty when the next session starts. The next `/start` will notice and offer to wrap up first.

## Steps

1. **Check spec completion.** For each spec under `areas/<area>/specs/` with work done in this session:
   - If every task in `tasks.md` is at a terminal `_Status:_` (`done` or `superseded`) and the work resolved the brief, write `outcome.md`. Use the template at `_framework/schema/spec-template/outcome.md.tmpl`. If any task is still `planned`/`in_progress`/`blocked`, the spec isn't done — say so rather than writing `outcome.md`.
   - If some tasks are still open, leave the spec in place; the next session can continue.

2. **Reconcile preserved pulse sections.** `pulse_compact.py` mechanically replays log entries — it can't tell on its own which open questions got resolved or whether the current focus is still accurate. Do this reconciliation explicitly:

   - **Open questions.** Read the current `pulse.md` Open questions section. For each entry, decide (from session context, with user confirmation when uncertain) whether it was resolved during this session. For each resolved one, append a `question-closed` event to `_journal/pulse.log` before compacting:
     ```
     ## [YYYY-MM-DD HH:MM] question-closed <role>
     <1-2 line resolution>
     → closes: <verbatim question text>
     ```
     One entry may include multiple `→ closes:` directives if several questions were retired together. Use the exact question text as it appears in `pulse.md`; matching tolerates case and trailing punctuation.

   - **Current focus.** Read the current focus. If it references work that has now completed (e.g. "Started spec X" where the spec is now done), append a `focus-shift` event resetting it. If the next direction is clear, the focus-shift describes the new focus; otherwise reset to a neutral placeholder:
     ```
     ## [YYYY-MM-DD HH:MM] focus-shift <role>
     _(set when work begins)_
     ```

3. **Compact pulse.** Run:
   ```
   python _framework/tools/pulse_compact.py areas/<area>
   ```
   (Or with no argument to compact every area and commons.) This:
   - Verifies that filed kb pages from the log exist (warns if not).
   - Regenerates pulse.md's "Recent decisions", "Active concepts under test", and "Recent findings" sections from current kb state.
   - Preserves "Current focus" and "Open questions", updating them from any `focus-shift`, `question`, and `question-closed` log entries this session.
   - Truncates `_journal/pulse.log`.

   If pulse_compact reports any missing-filed-path warnings, that means a journal entry referenced a kb page that doesn't exist. Create the missing page (it was probably forgotten during `/implement`) or fix the journal entry, then re-run.

4. **Verify lint.** Run:
   ```
   python _framework/tools/lint.py
   ```
   Fix any errors. The session is not wrapped up if lint is dirty — leave the journal in place and ask the user how to address the issues.

5. **Record session_end telemetry.** Gather:
   - **pages_cited** — every `[[wikilink]]` you referenced in your own outputs this session. Include their paths.
   - **bodies_loaded** — any pages whose body you read beyond the preload tier (i.e., pages from `## Preload context (frontmatter only)` patterns whose body you ended up loading, plus any pages outside preload entirely).

   Run:
   ```
   python _framework/tools/telemetry.py session-end \
       --cited "<comma-separated paths>" \
       --loaded "<comma-separated paths>"
   ```

6. **Summarize.** Tell the user, in 3–5 lines:
   - What was accomplished (which tasks/specs).
   - What's still open.
   - Any open questions surfaced during the session.

7. **Ask what's next, in one line.** End with: *"Continuing in this role, switching role, or
   done?"* Then follow their answer:

   - **Continuing** — nothing is required *for the role*: wrap-up didn't un-adopt anything (see
     the note below), so the preload is still loaded and re-running `/start` would be busywork.

     But check the context size before saying "just keep going." **Right after a wrap-up is the
     safest moment in the whole cycle to `/clear`** — the journal is compacted, specs are
     finalized, lint is clean, so there is nothing in the conversation that isn't also on disk.
     If the context is large, say so and offer the sequence: `/clear`, then `/start <role>` to
     reload the preload. Waiting until it's larger only makes the same clear more expensive.

     How to judge it: the status line shows `ctx <N>k` and marks it `!` past the configured
     threshold (`kb_vitals.context_restart_threshold_tokens`, default 400k), and `/kb-vitals`
     reports it in words. Treat the threshold as a prompt, not a rule — a session well under it
     that has churned through a lot of unrelated material is still a good candidate, and a long
     session in the middle of one focused task may be worth keeping intact.

     `/clear` is the right tool here, not a quit-and-relaunch. A full restart is the fix for hooks
     that never fired, which is a different problem with its own `/kb-vitals` vital.
   - **Switching role** — `/clear`, then `/start <new-role>`. The `/clear` is the load-bearing
     step and the one that gets forgotten: without it the new role starts with the old role's
     context still loaded, which is the failure this prompt exists to catch.
   - **Done** — nothing further. Suggest `git commit` if the work isn't committed; the project is
     in a clean, journaled state.

   Keep it to one line and one answer. This is a routing question, not a checklist — if the user
   has already said what they're doing next, skip it rather than asking redundantly.

## Notes

- `pulse_compact.py` is idempotent. If you run it twice, the second run is a no-op (empty log, no new state).
- The line cap on pulse.md is enforced by lint rule 7 (default 80 lines). If `pulse_compact.py` exits with code 1, the pulse went over cap — review what was added and decide what to promote out (some decisions or findings may be ripe to leave the "recent" section and live only in their kb pages).
- **What counts as "cited" for telemetry?** A page is cited if you referred to it in output the user saw — either you used a `[[wikilink]]` to it, or you summarized its content in your response. A page that was preloaded but never referenced is not cited.
- **What counts as "loaded beyond preload"?** Anything where you read the full body and it wasn't in `## Preload context (full)`. Frontmatter-tier pages whose bodies you read count.
- Don't agonize over getting telemetry exactly right. Best-effort is fine; the data is for trend analysis (which preloads aren't being used) not precise accounting.
- If `por` is enabled, also update `POR.md` for the area if anything material shifted: phase change, completed workstream, new dependency.
- After `/wrap-up` is the natural place to `git commit`. The skill itself doesn't commit, but the project is in a clean, journaled state ready for one.
- **Wrap-up does not un-adopt the role** (this is what step 7's "continuing" branch rests on). It closes a working session in the *bookkeeping* sense — journal compacted, specs finalized, lint clean — but it never touches `_session/<session-id>.json`. The adopted role and area survive, the preload is still loaded, and `/kb-vitals` and the status line stay scoped to that role. Only the session-start hook (new session) and the session-end hook (process exit) clear it.

  So if the user carries on in the same role, **nothing is required** — keep working, and new pulse entries accumulate in the freshly-truncated log. Re-run `/start` only when the role is *changing*, or after a `/clear` or restart, which is what actually discards context.

  Two things do drift if a session continues well past a wrap-up, neither blocking: the `session_end` telemetry event is now unpaired (a second `/wrap-up` logs a second one against one `session_start`), and `started_at` still holds the original adoption time, so `/kb-vitals`'s stale-preload check may flag pages this session itself updated. Re-running `/start` restamps both. Offer it as tidiness, never as a prerequisite.
