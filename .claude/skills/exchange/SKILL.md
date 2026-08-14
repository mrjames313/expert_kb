---
name: exchange
description: Open a Q&A exchange with another area. Files a question under exchanges/<asker>--<responder>/, which the responder picks up via /respond-exchange. Requires the multi_area capability.
---

# /exchange

Files a question to another area's role(s). The responder picks it up via `/respond-exchange`; the asker eventually closes via `/close-exchange`.

## When to use

- The role needs information that lives in another area's domain.
- The question is non-trivial enough that `/answer-from-kb` (reading the other area's kb directly) won't answer it — it needs the other area's role to engage.
- You'd otherwise be tempted to read deeply into another area's kb bodies (which lint rule 16 surfaces as a heavy pattern).

Don't use `/exchange` for:
- Simple lookups against another area's existing kb — use `/answer-from-kb` instead.
- Questions you can answer from `commons/kb/` — those are project-wide; just read.

## Steps

1. **Confirm the target area.** Default to the area named by the user. If multiple areas could plausibly answer, ask. The exchange goes one-to-one — pick one responder area.

2. **Determine the exchange directory.** Sort the two area names alphabetically; the dir is `exchanges/<a>--<b>/` regardless of who's asking whom. Example: research asks engineering → `exchanges/engineering--research/`.

   If the directory doesn't exist, create it with:
   - `OWNERS` — a one-line list of both areas: `engineering, research`.
   - `README.md` — boilerplate explaining the exchange is between these two areas.
   - `index.md` — empty index that the new question will be added to.

3. **Pick a question slug.** Format: `q-YYYY-MM-DD-<short-name>`. The full id becomes `ex-YYYY-MM-DD-<short-name>`.

4. **Write the question file** at `exchanges/<a>--<b>/<id>.md`:
   ```yaml
   ---
   id: ex-2026-05-15-thermal-sensitivity
   status: open
   asker_area: <your area>
   asker_role: <your role>
   responder_area: <target area>
   created: 2026-05-15
   relevant_to:
     - <tag>
     - <tag>
   ---

   # Question

   2–6 sentences. Be specific. State what you need to *do* with the answer
   (so the responder knows the right level of detail).

   ## Context

   `[[wikilinks]]` to your area's pages that motivated the question, and any
   commons pages that bear on it.

   # Response

   _(filled in by responder)_

   # Follow-up

   _(optional; asker can drill in after a response)_
   ```

5. **Append to the index.** Add a line to `exchanges/<a>--<b>/index.md`:
   ```markdown
   - [[<id>]] — open, asked by <asker_role>@<asker_area> on YYYY-MM-DD
   ```

6. **Verify.** Run `python _framework/tools/lint.py`. Exchange files have minimal lint requirements; the main thing is that wikilinks in the Context section resolve.

7. **Brief the user.** Note that the question is open and the responder area is on the hook. Suggest moving on to other work — exchanges don't block.

## Notes

- Exchanges are async. Don't expect an immediate response; the responder may not be in session.
- Keep the question scoped. If you need answers to five things, file five exchanges (or one exchange with a clearly numbered list and a note that partial responses are fine).
- The responder may push back. Their response could be "this question is malformed — can you clarify?" or "this isn't really our area; try X." That's normal — close this exchange and file a new one if needed.
- Don't bypass an exchange by editing the other area's kb directly. Even with `multi_area` enabled, write boundaries hold — `/exchange` is the right channel.
- Filing an exchange does **not** get a pulse `question` event. The exchange is tracked by its own index (`exchanges/<a>--<b>/index.md`) and `status` lifecycle; a `question` event would duplicate it into your area's pulse "Open questions" section, and since closing an exchange emits no `question-closed`, that line would never clear. Reserve `question` events for open questions you're *not* routing through an exchange.
- The full protocol lives at `_framework/schema/exchange-protocol.md` if anything here is ambiguous.
