---
name: kb-vitals
description: Show operational state and the recommended next actions — what the human owes (decisions, acks, promotions) project-wide, plus the current role's local hygiene (wrap-up due, over-cap pulse, blocked/complete specs, a stale/bloated-session restart nudge). Run when orienting, when unsure what to do next, or periodically to stay on top of the workflow.
---

# /kb-vitals

Scans state and surfaces the next actions to keep the workflow healthy — each with the command to run. Two scopes: **human vitals** (project-wide — things only you can resolve) and **role vitals** (the currently adopted area/role's local hygiene). Reads the adopted role/area from this session's `_session/<session-id>.json` (written by `/start`), so it needs no arguments.

## When to use

- When you're unsure what to work on or what's outstanding ("what's pending?", "where do I stand?", "anything I owe?").
- Periodically during a session to stay on top of the framework's expectations.
- Right after `/start`, or before ending a session, as a check.

## Steps

1. **Run the scan:**
   ```
   python _framework/tools/kb_vitals.py
   ```

2. **Show its output verbatim.** The tool already formats the result (human block, then role block, each with the command to run). **Reproduce that output as-is in a fenced code block** — do not re-narrate, re-order, or summarize it. The point is that the human sees the actual tool output, not your paraphrase.

3. **Add one line, then offer to act.** Below the output, add at most a single line pointing at the most pressing item, then offer to run it (e.g. "Want me to run `/wrap-up`?"). Let the human choose — don't start resolving items unprompted.

## Notes

- **No role adopted?** The role block will say so — run `/start` first for the role-scoped checks. Human vitals still show.
- **Restart nudge.** When it reports the context is large, recommend a **full restart (quit + relaunch)**, not just `/clear` — `/clear` reuses the same process (and, until the hooks fix lands, the same stale hook snapshot). The token figure is read live from the session transcript.
- **Cheap by design.** It does not run lint (`/check` does that); it reads cheap signals only. Capability-gated checks (exchanges) are silently skipped when the capability is off.
- It reads this session's state file and the KB; it changes nothing. State is per-session, so with two sessions open in one repo each reports its own adopted role.
