---
name: plan
description: Turn a brief into a plan, then—after human approval—a tasks file, under areas/<area>/specs/<name>/. Use to scope a piece of work before implementation. Plans precede /implement.
---

# /plan

Reads a spec brief (or drafts one with the user) and writes `plan.md`. After the human approves the plan in conversation, populates `tasks.md` and prepares the work for `/implement`.

## When to use

- User wants to start a new piece of work that's bigger than a single edit.
- An existing brief.md exists but lacks a plan.
- A previous plan was abandoned and the user wants to start fresh (use `/replan` instead if the existing plan is partially valid).

## Steps

1. **Locate or create the spec directory.** Specs live at `areas/<area>/specs/<spec-name>/`. The spec name should be a short slug (e.g. `noise-floor-characterization`).

   - If the user names an existing spec, use that directory.
   - If new, create `areas/<area>/specs/<spec-name>/` and ask the user for a brief if one isn't supplied.

2. **Draft or refine `brief.md`.** A brief is 1–2 paragraphs answering: what is the goal, why does it matter, what's the success criterion. It should fit in the user's head. Use the template at `_framework/schema/spec-template/brief.md.tmpl` as a starting point if needed.

3. **Search the kb for relevant context.** Before planning, look at:
   - `areas/<area>/kb/findings/` and `decisions/` — what's already known.
   - `areas/<area>/kb/concepts/` with `status: under_test` — what's currently being investigated.
   - Cite the relevant pages in `plan.md`.

4. **Write `plan.md`.** Use the template at `_framework/schema/spec-template/plan.md.tmpl`. The plan should cover:
   - **Approach** — how you'll tackle the goal, in 3–6 sentences.
   - **Milestones** — checkpoints you'll hit along the way.
   - **Open questions** — anything the user needs to decide before work starts.
   - **Citations** — `[[wikilinks]]` to relevant kb pages.

5. **Stop at the phase gate.** Show `plan.md` to the human and get their approval **in conversation before writing `tasks.md`**. This is a mandatory human gate — the plan template states it, and CLAUDE.md's spec lifecycle makes each transition a human decision. If they want changes, revise `plan.md` and re-confirm. Don't proceed to tasks until they approve.

6. **Write `tasks.md`** (only after approval). Use the template at `_framework/schema/spec-template/tasks.md.tmpl`. Each task should be:
   - **Small** — completable in one `/implement` invocation (rule of thumb: under an hour of focused work).
   - **Concrete** — phrased as "do X" not "investigate Y".
   - **Structured per the template** — a `### T<n>: <title>` heading with the annotation lines `_Boundary:_`, `_Depends:_`, `_Status:_ planned`, and `_Owner role:_`. Task status lives on the `_Status:_` line (values: `planned | in_progress | done | blocked | superseded`), **not** a checkbox.
   - Marked (via `_Depends:_` and the description) with which kb pages it depends on or will produce.

7. **Record in pulse.log.**
   ```
   ## [YYYY-MM-DD HH:MM] focus-shift <role>
   Started spec <spec-name>: <one-line goal from brief.md>.
   ```

8. **Verify.** Run `python _framework/tools/lint.py`. Lint should stay clean (plan.md and tasks.md don't have frontmatter requirements; nothing to break).

9. **Hand off.** Tell the user the plan is ready and suggest `/implement` for the first task.

## Notes

- Don't include an `outcome.md` yet. That gets written at `/wrap-up` after work completes, not before.
- If the user wants a very small change (one finding, one edit), `/plan` is overkill — go straight to making the edit and journaling it. `/plan` is for work that needs scoping.
- The plan can cite concepts under test as evidence. If the plan depends on a concept being supported and it isn't, mark this as a precondition in the plan (a task to validate the concept).
- If, while planning, you discover the work spans multiple areas: ask the user. With `multi_area` enabled, use `/exchange` to coordinate. Without it, the user has to choose one area to own the work, or run `/add-area` to create a new area.
- A plan can reference earlier specs that established context. An `outcome.md` lives outside `kb/`, so link it as a **relative markdown link**, not a wikilink — `[2026-04-noise-floor](../2026-04-noise-floor/outcome.md)` — per `link-conventions.md`. Wikilinks in a plan are for kb pages, and Rule 2 checks that each one resolves.
