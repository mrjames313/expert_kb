---
name: exchange
description: File a cross-area exchange — a query (ask another area a question) or a brief (push a conclusion to another area's roles). Requires the multi_area capability.
---

# /exchange

Files an exchange to another area. Two kinds:

- **query** (default) — ask another area's role(s) an authoritative question. They answer via `/respond-exchange`; you review and close via `/close-exchange`.
- **brief** — push a conclusion that specific role(s) in another area need but wouldn't know to ask for. No response is expected; each targeted role disposes of it (preload / file / cite) via `/close-exchange`.

Invoke as `/exchange <other-area> <text> [--kind query|brief]`.

## When to use

**As a query** (`--kind query`, the default):
- The role needs information that lives in another area's domain.
- Non-trivial enough that `/answer-from-kb` won't answer it — it needs the other area's role to reason.
- You'd otherwise deep-read another area's kb bodies (lint rule 16 flags this).

**As a brief** (`--kind brief`):
- You've concluded something a specific role in another area needs — a finding, a decision, a changed assumption — that they wouldn't know to ask about.
- The push is targeted and one-time. If it's project-wide ("everyone needs this"), use `/propose-promotion` instead — commons is that channel.

Don't use `/exchange` for:
- Simple lookups against another area's kb — use `/answer-from-kb`.
- Anything answerable from `commons/kb/` — just read it.

## Steps

1. **Confirm kind and target area.** Kind comes from `--kind` (default `query`). Target area from the user; if several could plausibly answer a query, ask. An exchange is one-to-one on areas — pick one `to_area`.

2. **For a brief, determine the target roles.** Ask which role(s) in `to_area` the brief is for, or "all." List `areas/<to_area>/roles/*/` to resolve "all" into an explicit set. Record them as `to_roles`, and copy the same list into `open_for`. (Queries skip this — any role in `to_area` may respond.)

3. **Determine the exchange directory.** Sort the two area names alphabetically → `exchanges/<a>--<b>/`, regardless of direction. If it doesn't exist, create:
   - `OWNERS` — one line: `<a>, <b>`.
   - `README.md` — boilerplate: exchanges between these two areas.
   - `index.md` — empty index.

4. **Pick a slug and id.** Slug is a short kebab name; the id is `ex-YYYY-MM-DD-<slug>`. The file is `exchanges/<a>--<b>/<id>.md`.

5. **Write the exchange file.**

   **Query:**
   ```yaml
   ---
   id: ex-2026-05-15-thermal-sensitivity
   kind: query
   status: open
   from_area: <your area>
   from_role: <your role>
   to_area: <target area>
   created: 2026-05-15
   relevant_to: [<tag>, <tag>]
   ---

   # Question

   2–6 sentences. Be specific. State what you need to *do* with the answer
   (so the responder knows the right level of detail).

   ## Context

   Area-prefixed wikilinks to the pages that motivated the question, e.g.
   [[<your-area>:concepts/c-...]], plus any commons pages that bear on it.

   # Response

   _(filled in by responder)_

   # Follow-up

   _(optional; asker can drill in after a response)_
   ```

   **Brief:**
   ```yaml
   ---
   id: ex-2026-05-15-drift-model-update
   kind: brief
   status: open
   from_area: <your area>
   from_role: <your role>
   to_area: <target area>
   to_roles: [<role>, <role>]
   open_for: [<role>, <role>]      # same list as to_roles
   created: 2026-05-15
   relevant_to: [<tag>]
   ---

   # Brief

   2–5 sentences. State the conclusion and *why it matters to the recipient(s)* —
   what they should reconsider or act on.

   ## Context

   Area-prefixed wikilinks to your pages that back the claim, e.g.
   [[<your-area>:findings/f-...]].

   # Dispositions

   _(each targeted role records what it did on close)_
   ```

6. **Append to the index.** In `exchanges/<a>--<b>/index.md`:
   ```markdown
   - [[<id>]] — <kind> from <from_role>@<from_area>, open, YYYY-MM-DD
   ```

7. **Verify.** Run `python _framework/tools/lint.py`; confirm the repo stays clean. (Exchange files aren't kb pages, so their wikilinks aren't lint-checked — still point them at real pages.)

8. **Brief the user.**
   - Query: the question is open and the responder area is on the hook. Move on — exchanges don't block.
   - Brief: it's filed for `<to_roles>`; they'll pick it up at their next `/start`. Nothing is owed back to you.

## Notes

- Exchanges are async. A query's responder may not be in session; a brief's recipients act on their own schedule.
- Keep it scoped — one question or one conclusion per exchange.
- A query's responder may push back ("malformed — can you clarify?" / "not our area; try X"). That's normal — close and refile if needed.
- A brief expects no response. If you find yourself wanting an answer back, file a query instead.
- Don't bypass an exchange by writing into the other area's kb or role files directly — write boundaries hold. `/exchange` is the channel.
- Filing an exchange does **not** get a pulse `question` event — it's tracked by its own index and `status`. (A `question` event would duplicate it into your pulse "Open questions" and, since closing an exchange emits no `question-closed`, never clear.) Reserve `question` events for open questions you're *not* routing through an exchange.
- The full protocol lives at `_framework/schema/exchange-protocol.md` if anything here is ambiguous.
