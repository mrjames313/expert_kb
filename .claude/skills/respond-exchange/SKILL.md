---
name: respond-exchange
description: Pick up and answer an open exchange directed at the role's area. Updates the question file with a response and sets status to answered. Requires the multi_area capability.
---

# /respond-exchange

Picks up an open **query** where the role's area is the `to_area`, drafts a response, and updates the exchange file. (Briefs — `kind: brief` — have no response step; they go straight to disposition via `/close-exchange`.)

## When to use

- A `/start` scan showed an open query in `exchanges/<a>--<b>/` with `to_area` matching the adopted area.
- An INBOX staleness heads-up surfaced a pending query.
- The user explicitly invokes `/respond-exchange <id>`.

## Steps

1. **Find the exchange.** Either:
   - User named it by id → read `exchanges/*/<id>.md` directly.
   - User didn't name one → scan `exchanges/*/` for files with `kind: query`, `status: open`, and `to_area:` matching the role's area; list them and let the user pick.

2. **Read the question carefully.** Note:
   - Exactly what's being asked.
   - The `Context` section — which pages of the asker's the question relates to.
   - The `relevant_to` tags — what aspect of the role's area to focus on.

3. **Research the answer from your area's kb.** Just like `/ask`:
   - Search `kb/findings/`, `kb/decisions/`, `kb/concepts/`.
   - Read relevant page bodies.
   - Cite with area-prefixed `[[<your-area>:findings/f-...]]` wikilinks (the asker is in another area, so the prefix makes the source clear).

4. **Determine the response quality.** Three possibilities:
   - **Direct answer** — you can answer from existing kb. Write a concise response with citations.
   - **Provisional answer** — kb is incomplete but you can offer current best understanding. Mark it provisional explicitly.
   - **Deflect** — the question is outside your area's scope, or so vague you can't answer. Respond explaining why, suggest a different responder area or a clarification.

5. **Update the question file.** Fill in the `# Response` section:
   ```markdown
   # Response

   _Responded by <your-role>@<your-area> on YYYY-MM-DD._

   <Your answer in 1–4 paragraphs. Cite with area-prefixed [[<your-area>:...]] wikilinks.>

   <If provisional, note that explicitly: "This is current best understanding;
   the underlying concept is at `under_test` status.">

   <If deflecting, explain why and suggest next step.>
   ```

   Update the frontmatter `status:` to `answered`.

6. **Update the exchange's index.** In `exchanges/<a>--<b>/index.md`, change the entry's status from `open` to `answered`.

7. **Record in pulse.log** in your area's `_journal/pulse.log`:
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Answered exchange <id> from <from_area>: <one-line summary>.
   ```

8. **Verify.** Run `python _framework/tools/lint.py`. Any `[[wikilinks]]` in your response must resolve.

9. **Brief the user.** Tell them the response is filed. The asker will pick it up at their next `/start` (or by direct invocation of `/close-exchange`).

## Notes

- A response can change the question. If reading the question made you realize the asker is misframing the problem, say so in the response and suggest the reframing. The asker can choose to file a new exchange with the corrected question.
- You may file new findings/concepts in your own area as part of researching the answer. That's normal — the question may have surfaced a gap. Record those in pulse.log as usual.
- You don't write to the asker's area. Your response lives in the exchange file (which is in a neutral exchange directory, not in either area's kb). The asker decides what becomes part of their kb via `/close-exchange`.
- If you can't fully answer but can answer partially, do so. The asker can either close (accepting the partial) or file a follow-up.
- An exchange can stay in `answered` status indefinitely until the asker closes it. Lint rule 14 (configurable warning, off by default) can surface stale-answered exchanges.
