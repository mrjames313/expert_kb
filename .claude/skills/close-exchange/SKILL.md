---
name: close-exchange
description: Dispose of and close an exchange you received — a query you asked (review the answer) or a brief addressed to your role. Preload / file / cite the information, then close. Requires the multi_area capability.
---

# /close-exchange

The disposition step: the party that *received* information decides what to do with it and closes. That's the **asker** for a query (they received the answer) and **each targeted role** for a brief (they received the statement).

Disposition options are the same for both: **preload** the referenced page into your role, **file/cite** it in your kb, or **none**.

## When to use

- A query you filed now has `status: answered` (`from_area` is your area) — review and close.
- A brief addressed to your role is open with your role still in `open_for` (`to_area` is your area) — act on it.
- The user explicitly invokes `/close-exchange <id>`, or a `/start` scan surfaced one.

## Steps

1. **Find the item.** By id, or scan `exchanges/*/`:
   - Answered queries: `kind: query`, `status: answered`, `from_area` == your area.
   - Open briefs for you: `kind: brief`, `status: open`, `to_area` == your area, your role ∈ `open_for`.

2. **Read the thread.**
   - Query: Question + Context + Response.
   - Brief: Brief + Context + any existing Dispositions.

3. **(Query only) Decide on follow-up.**
   - **Satisfied** — the response answers it. Continue.
   - **Follow-up needed** — fill the `# Follow-up` section and set `status: follow_up`; the responder picks it up again. (Stop here — not yet closed. The index tracks the new status on the next lint run.)
   - **Insufficient / abandoned** — close without incorporating; note the direction taken.

   Briefs have no follow-up path — proceed straight to disposition.

4. **Dispose — decide what to do with the information.** Pick one or more:
   - **preload** — add the referenced page (`[[area:findings/f-…]]`) to *your role's* preload. Edit `areas/<your-area>/roles/<your-role>/role.md` — the `## Preload context (full)` section for a page you'll cite often, or `## Preload context (frontmatter only)` for a directory pattern. **Confirm with the human first** — preloads are human-owned (`H`).
   - **file / cite** — write a finding/concept/decision in your area kb, citing the exchange as provenance:
     ```yaml
     provenance:
       kind: external
       retrieved: 2026-05-15
       raw_path: exchanges/<a>--<b>/<exchange-id>.md
     ```
     (The exchange is a repo file, but treat it as "external" — it came from another area's role.)
   - **none** — nothing durable. Still recorded, so the item clears.

5. **Record the disposition and close.**

   **Query** — set frontmatter `status: closed`, add `closed_on: YYYY-MM-DD` and `closed_by: <role>`, and append:
   ```markdown
   # Closure

   _Closed by <role>@<area> on YYYY-MM-DD._

   <What (if anything) became part of your kb or preload, citing the new pages;
   or the direction taken if nothing was incorporated.>
   ```

   **Brief** — append your role's entry under `# Dispositions`:
   ```markdown
   ## <your-role> — YYYY-MM-DD
   <preloaded / filed [[...]] / cited / none> — <one line>.
   ```
   Then remove your role from `open_for`. If `open_for` is now empty, set `status: closed` and add `closed_on: YYYY-MM-DD`. If not, leave `status: open` — the brief stays surfaced for the remaining roles.

6. **Record in pulse.log** (your area):
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Disposed exchange <id> (<kind>): <what you did with it>.
   ```
   If you filed kb pages, also add the appropriate `finding`/`concept`/`decision` entries.

7. **Verify.** Run `python _framework/tools/lint.py`. New kb pages need complete frontmatter; any preload edits should reference existing files. Rule 22 checks the frontmatter you just changed — in particular that a brief is `closed` exactly when `open_for` is empty — and the run regenerates the pair's `index.md`, so there is no index line to update by hand.

8. **Brief the user.** Summarize what you did with the information, and — for a brief — who (if anyone) still owes a disposition.

## Notes

- **The receiver disposes and closes** — the asker for a query, each targeted role for a brief. A query's responder never closes; they only respond.
- **Briefs close incrementally.** You clear only your own role from `open_for`; the brief is fully `closed` only when the last targeted role disposes.
- **Declining is an explicit disposition** (`none`). Record it and clear your role from `open_for` — otherwise an indifferent role keeps the brief open forever.
- **Preload edits are human-confirmed.** The disposition proposes; the human approves the `role.md` change. (An automated preload-diff proposer is future work; for now you make the edit by hand.)
- You can dispose with `none` and still close — not every exchange produces durable knowledge; sometimes it just unblocks a decision.
- If the same answer keeps coming up, that's a signal to **promote it to commons** via `/propose-promotion`.
- Don't reopen a closed exchange. If new questions arise, file a fresh `/exchange` referencing the closed one in its Context.
- Staleness lint surfaces answered queries and briefs with a non-empty `open_for` that have lingered.
