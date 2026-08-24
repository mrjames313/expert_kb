---
name: review
description: Independent review of completed work against its spec. Reads the spec and the implementer's output, produces a verdict file (APPROVE | OBJECT | ABSTAIN) with rationale. Requires the formal_review and task_subagents capabilities.
---

# /review

Independent review of a completed task or spec. Run by a reviewer role — a stripped-down variant of the implementer role that has the same context but writes only verdict files.

## When to use

- An implementer finished a task in a spec, and the spec is configured for review (or the user explicitly requests one).
- A spec is complete and ready to merge — the user wants an independent look before `/wrap-up` writes the outcome.
- Most commonly invoked by an orchestrator after `/implement` completes, when `formal_review` is enabled.

A review is run by the **reviewer role**, not by the implementer. The orchestrator spawns the reviewer in a fresh subagent (which `task_subagents` requires); the subagent's job is to do this skill and exit.

## Steps

1. **Identify the scope.** Either:
   - User/orchestrator named a task: review just that task's output (changed files, new kb pages, journal entries).
   - User/orchestrator named a spec: review the whole spec — every task's output plus the overall plan execution.

2. **Re-read the spec.** From `areas/<area>/specs/<spec>/`:
   - `brief.md` — what was supposed to be accomplished.
   - `plan.md` — how it was supposed to be approached. Note any `## Revision` sections from `/replan`.
   - `tasks.md` — what tasks were declared and which are done.

3. **Re-read the work.** Read what the implementer produced:
   - Any new kb pages under `kb/findings/`, `kb/concepts/`, `kb/decisions/`.
   - Any code or data changes the spec implied.
   - The relevant pulse.log entries (or the regenerated pulse.md sections).

4. **Evaluate against the spec.** Three questions:
   - **Does the work do what the brief asked?** Match the outputs to the success criterion in brief.md.
   - **Is the kb sound?** New findings cite their provenance. New concepts have evidence (if at `under_test`+). New decisions list alternatives considered. Wikilinks resolve.
   - **Are there gaps?** Tasks at `_Status:_ done` whose outputs are missing or thin. Loose ends that should have been journaled as `question` events but weren't.

5. **Pick a verdict.** Exactly one of:
   - **APPROVE** — the work substantively meets the spec. Minor stylistic notes can go in the verdict but don't block.
   - **OBJECT** — something material is wrong: the work doesn't meet the brief, kb claims are unsupported, or critical loose ends exist. Verdict must include concrete rationale and what would change it to APPROVE.
   - **ABSTAIN** — this work doesn't materially affect the reviewer's area's interests, or the reviewer doesn't have enough context to judge. Briefly explain why.

6. **Write the verdict file.** Path: `areas/<area>/specs/<spec>/verdicts/<reviewer-role-name>.md`. (Create the `verdicts/` directory if needed.)
   ```yaml
   ---
   reviewer_role: <your-reviewer-role-name>
   reviewer_area: <your-area>
   reviewed_on: 2026-05-15
   target: spec | task
   target_id: <spec-name> or <spec-name>/task-N
   verdict: APPROVE | OBJECT | ABSTAIN
   ---

   # Review of <target>

   ## Verdict: <APPROVE | OBJECT | ABSTAIN>

   ## Summary

   1–3 sentences on what was reviewed and the headline assessment.

   ## What's solid

   - <bullet> with [[wikilink]] citations to specific pages
   - <bullet>

   ## Concerns

   (Required for OBJECT; optional for APPROVE; explain abstention for ABSTAIN.)

   - <bullet> — what's wrong, with a citation to the offending page or task
   - <bullet> — what would change it to APPROVE

   ## Notes

   (Optional stylistic or future-direction notes. Non-blocking.)
   ```

7. **Verify.** Run `python _framework/tools/lint.py`. Verdict files have minimal frontmatter requirements but wikilinks in the body should resolve.

8. **Exit.** The reviewer subagent does not journal to pulse.log, does not run `/wrap-up`, does not produce anything besides the verdict file. The orchestrator picks up the verdict and acts on it.

## Notes

- The reviewer has **read access to the full repo** but **writes only to the verdict file** for the target under review. This is enforced by the reviewer role's "Operating boundaries" section (auto-generated when `formal_review` is enabled).
- A reviewer can OBJECT to their own area's work. There's no in-area bias guard — the reviewer is meant to be an independent set of eyes.
- Don't review work you implemented yourself. The orchestrator should not spawn a reviewer whose role is the same as the implementer; doing so would be self-review.
- Multiple reviewers from different areas may file separate verdicts on the same spec (especially if it has cross-area implications). Each writes their own verdict file; the implementer (or coordinator) reconciles.
- An OBJECT verdict doesn't auto-revert the work. The implementer reads the verdict and decides: revise via `/implement`, restructure via `/replan`, or push back via a conversation with the user.
- An ABSTAIN verdict is a legitimate outcome — better than a half-confident APPROVE or a vague OBJECT.
