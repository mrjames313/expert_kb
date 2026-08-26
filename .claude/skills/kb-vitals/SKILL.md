---
name: kb-vitals
description: Show operational state and the recommended next actions — what the human owes (decisions, acks, promotions) project-wide, plus the current role's local hygiene (wrap-up due, over-cap pulse, blocked/complete specs, a stale/bloated-session restart nudge). Run when orienting, when unsure what to do next, or periodically to stay on top of the workflow.
---

# /kb-vitals

Scans state and surfaces the next actions to keep the workflow healthy — each with the command to run. Two scopes: **human vitals** (project-wide — things only you can resolve) and **role vitals** (the currently adopted area/role's local hygiene). Reads the adopted role/area from `_session.json` (written by `/start`), so it needs no arguments.

## When to use

- When you're unsure what to work on or what's outstanding ("what's pending?", "where do I stand?", "anything I owe?").
- Periodically during a session to stay on top of the framework's expectations.
- Right after `/start`, or before ending a session, as a check.

## Steps

1. **Run the scan:**
   ```
   python _framework/tools/kb_vitals.py
   ```

2. **Present it next-actions-first.** Show the human block first (project-wide decisions/acks — the blocking ones), then the role block (current area). Lead with what to *do*, not raw counts. If a section is clean, say so briefly.

3. **Offer to act, don't auto-act.** Each vital names a command. Offer to run the most pressing one (e.g. `/wrap-up` if pulse is over cap, or walk through the "Awaiting your ack" pages), but let the human choose. Don't start resolving items unprompted.

## Notes

- **No role adopted?** The role block will say so — run `/start` first for the role-scoped checks. Human vitals still show.
- **Restart nudge.** When it reports the context is large, recommend a **full restart (quit + relaunch)**, not just `/clear` — `/clear` reuses the same process (and, until the hooks fix lands, the same stale hook snapshot). The token figure is read live from the session transcript.
- **Cheap by design.** It does not run lint (`/check` does that); it reads cheap signals only. Capability-gated checks (exchanges) are silently skipped when the capability is off.
- It reads `_session.json` and the KB; it changes nothing.
