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

1. **Load orientation — always, before anything else.** Run:
   ```
   bash _framework/hooks/session-start.sh --orient-only
   ```
   This prints `areas-index.md`, `INBOX.md`, and the pulse-log state. Run it **whether or not the
   user named a role**: the INBOX may hold "Needs decision" items meant to block work, and a role
   named up front is not a reason to skip them.

   Do this even though a SessionStart hook may have printed the same block. It's cheap and
   idempotent (`--orient-only` performs no writes), and it is what makes `/start` correct on its
   own. Claude Code snapshots hook configuration at *process start*, so in a workspace where
   setup wrote `.claude/settings.json` into an already-running process — the documented adoption
   path — no hook fires for that entire session, and `/clear` does not help because it reuses the
   process. Treat the hook as an optimization, never as a precondition.

2. **Determine the role.** If the user named one (e.g. `/start researcher`), use it. Otherwise:
   - Use the `areas-index.md` catalogue from step 1 to see which roles exist.
   - Use the INBOX items from step 1 to see what work is pending and which areas it implicates.
   - If the user's intent is clear from a previous message, suggest a single role and confirm. If not, ask.

3. **Resolve the role file.** Find one of:
   - `areas/<area>/roles/<role>/role.md`
   - `commons/roles/<role>/role.md` (only if `coordinator` is enabled via the `por` capability)

   If the role file doesn't exist, ask the user whether they meant a different role or want to use `/add-area` to create one.

4. **Load preload context.** Follow the role file's `## Preload context (full)` section: read every listed file in full. Then follow `## Preload context (frontmatter only)`: for each directory pattern, read the frontmatter blocks (between leading and trailing `---`) of every `.md` under that path. Skip `index.md` files.

   Lines wrapped in `# capability: X` / `# end capability: X` markers are conditional. Only load them if capability `X` is enabled in `_framework/config.yml`.

5. **Record telemetry and session state.** Run:
   ```
   python _framework/tools/telemetry.py session-start --role <path-to-role.md>
   python _framework/tools/session_state.py adopt --role <role-name> --area <area-path>
   python _framework/tools/kb_vitals.py --refresh-cache
   ```
   The second line records the adopted role/area (and an adoption timestamp) in the git-ignored `_session/<session-id>.json`, so `/kb-vitals` and the status line can scope their role checks and detect a stale/bloated session. It keys on `$CLAUDE_CODE_SESSION_ID` automatically — one file per session, so adopting a role here never disturbs a concurrent session working as another role in the same repo. `<area-path>` is the role's area (`areas/<area>`, or `commons` for the coordinator). This is the authoritative writer — it overwrites whatever the session-start hook left, so it's correct even when hooks didn't fire.

   The third line refreshes the status line's vitals cache — the snapshot of the counts too expensive to compute per render (commons pages awaiting review, exchanges, preload staleness). It's cheap here, and it's what keeps the H/R indicators honest for the rest of the session; the session-start hook does the same, so this line matters most when hooks didn't fire.

   Show the user the preload cost in the telemetry output. If it's much higher than expected, suggest `/budget` to investigate.

6. **Orient to current state.** From the role's area:
   - Read `pulse.md` end-to-end. Note especially the "Current focus" and "Open questions" sections.
   - Read `_journal/pulse.log` if it's non-empty. (A non-empty log usually means the previous session didn't wrap up; offer to run `/wrap-up` first.)
   - If an in-progress spec lives under `areas/<area>/specs/`, read its `plan.md` and `tasks.md`.
   - **If `multi_area` is enabled**, scan `exchanges/*/` for items involving this area and surface them:
     - Queries with `status: open` or `follow_up` and `to_area` == this area → to answer (`/respond-exchange`). A `follow_up` is one the asker drilled into after your area answered; the responder cycle repeats.
     - Answered queries with `from_area` == this area → to close (`/close-exchange`).
     - Open briefs with `to_area` == this area where the adopted role is in `open_for` → to dispose (`/close-exchange`).

     Read only the frontmatter to triage; open a body when the user picks one to act on.

7. **Brief the user.** In one short paragraph: where the role left off, what's open, and one or two suggestions for what to work on next. Don't start working — wait for the user to choose.

## Notes

- If preload references files that don't exist on disk, the telemetry output's `missing_preload_files` will list them. Surface this — it usually indicates a stale role file (run `/framework prune` to clean it up).
- If `_framework/tools/telemetry.py` errors (missing venv, etc.), report the error to the user and continue the session without telemetry. The session will function; only the metrics layer is degraded.
- The `start` skill is the only one allowed to *adopt* a role. All other skills assume a role is already adopted.
- Do not load files beyond what the role file's preload sections specify. Loading more is the agent expanding its own context budget unilaterally; that's what `/budget` exists to surface and `/framework prune` to manage.
