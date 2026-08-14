---
name: start
description: Adopt a role and initialize a working session. Loads the role's preload context, records a session_start telemetry event, and briefs the user on current state. Run this at the beginning of any session, or whenever switching roles.
---

# /start

Picks a role, loads its preload context, records a session_start telemetry event, and orients the user to the area's current state.

## When to use

- The first thing in any working session.
- When switching roles mid-session (e.g. from `researcher` to `engineer`).
- After the session-start hook fires (if hooks are configured, the hook invokes this).

## Steps

1. **Determine the role.** If the user named one (e.g. `/start researcher`), use it. Otherwise:
   - Read `/areas-index.md` for the catalogue of roles available.
   - Read `/INBOX.md` for pending work and what areas it implicates.
   - If the user's intent is clear from a previous message, suggest a single role and confirm. If not, ask.

2. **Resolve the role file.** Find one of:
   - `areas/<area>/roles/<role>/role.md`
   - `commons/roles/<role>/role.md` (only if `coordinator` is enabled via the `por` capability)

   If the role file doesn't exist, ask the user whether they meant a different role or want to use `/add-area` to create one.

3. **Load preload context.** Follow the role file's `## Preload context (full)` section: read every listed file in full. Then follow `## Preload context (frontmatter only)`: for each directory pattern, read the frontmatter blocks (between leading and trailing `---`) of every `.md` under that path. Skip `index.md` files.

   Lines wrapped in `# capability: X` / `# end capability: X` markers are conditional. Only load them if capability `X` is enabled in `_framework/config.yml`.

4. **Record telemetry.** Run:
   ```
   python _framework/tools/telemetry.py session-start --role <path-to-role.md>
   ```
   Show the user the preload cost in the telemetry output. If it's much higher than expected, suggest `/budget` to investigate.

5. **Orient to current state.** From the role's area:
   - Read `pulse.md` end-to-end. Note especially the "Current focus" and "Open questions" sections.
   - Read `_journal/pulse.log` if it's non-empty. (A non-empty log usually means the previous session didn't wrap up; offer to run `/wrap-up` first.)
   - If an in-progress spec lives under `areas/<area>/specs/`, read its `plan.md` and `tasks.md`.
   - **If `multi_area` is enabled**, scan `exchanges/*/` for items involving this area and surface them:
     - Open queries with `to_area` == this area → to answer (`/respond-exchange`).
     - Answered queries with `from_area` == this area → to close (`/close-exchange`).
     - Open briefs with `to_area` == this area where the adopted role is in `open_for` → to dispose (`/close-exchange`).

     Read only the frontmatter to triage; open a body when the user picks one to act on.

6. **Brief the user.** In one short paragraph: where the role left off, what's open, and one or two suggestions for what to work on next. Don't start working — wait for the user to choose.

## Notes

- If preload references files that don't exist on disk, the telemetry output's `missing_preload_files` will list them. Surface this — it usually indicates a stale role file (run `/framework prune` to clean it up).
- If `_framework/tools/telemetry.py` errors (missing venv, etc.), report the error to the user and continue the session without telemetry. The session will function; only the metrics layer is degraded.
- The `start` skill is the only one allowed to *adopt* a role. All other skills assume a role is already adopted.
- Do not load files beyond what the role file's preload sections specify. Loading more is the agent expanding its own context budget unilaterally; that's what `/budget` exists to surface and `/framework prune` to manage.
