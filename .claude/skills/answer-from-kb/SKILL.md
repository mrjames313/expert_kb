---
name: answer-from-kb
description: Cheap, non-blocking lookup of another area's kb. Reads frontmatter (and selectively bodies) to answer questions that don't need the other area's role engaged. Requires the multi_area capability.
---

# /answer-from-kb

A lightweight cross-area read. Reads another area's `kb/index.md` and page frontmatter to answer a question without opening an exchange. The result is informational; no files are modified in the other area.

## When to use

- The role needs to know whether another area has a specific finding/decision/concept.
- The user asks "does <area> know X?" and the answer is likely in their kb.
- Before filing an exchange — check if the question is already answered.
- Quick orientation when assembling context for a plan.

Don't use `/answer-from-kb` when:
- The question requires the other area's role to reason (use `/exchange`).
- The question needs deep reading across many bodies (lint rule 16 flags this as a heavy pattern — file an exchange instead).

## Steps

1. **Identify the target area.** From the user's question, pick one area. If unclear, ask. Multi-area lookups should be sequential, not all at once.

2. **Start at the index.** Read `areas/<target-area>/kb/index.md` (the lint regenerates this). Scan the catalogue for entries whose title or summary matches the question's keywords.

3. **Read frontmatter blocks of candidate pages.** For each promising hit:
   - Read just the frontmatter (between leading and trailing `---`).
   - Check `status`, `summary`, and `relevant_to` tags.
   - If `when_to_load` is present, use it to decide whether the body is worth opening for *this* question — the field commonly names a cheaper alternative or scopes the page's task fit. Skip the body when `when_to_load` suggests it.
   - If frontmatter alone answers the question, stop there.

4. **Selectively read bodies.** If frontmatter isn't enough, read the full body of at most 2–3 pages. More than that and you're doing what `/exchange` is for. If you find yourself wanting to read more, stop and recommend `/exchange` instead.

5. **Synthesize an answer.** Just like `/ask`, but with explicit attribution to the *other area*:
   - Cite each page with an area-prefixed wikilink, e.g. `[[research:findings/f-...]]`, so the source area is explicit.
   - Distinguish between "their finding" (active, well-established) and "their hypothesis" (concept under test).
   - If the kb doesn't answer the question, say so. Don't speculate on behalf of the other area.

6. **No journaling.** `/answer-from-kb` is a read operation, like `/ask`. Don't append to pulse.log. The user can decide whether the answer affects their work; that follow-up is what gets journaled (as a finding, concept, or decision in your area).

7. **Recommend follow-up if needed.**
   - "This is your area's question now" — they file the finding/concept in their own kb.
   - "Worth promoting" — if the answer is broadly useful, suggest the *other area* run `/propose-promotion` on the relevant page (but don't do it yourself; it's their kb).
   - "Needs an exchange" — if the kb hint isn't enough, file an exchange.

## Notes

- This skill is *cheap*. Don't agonize. If after reading the index and 1–2 frontmatter blocks you don't have an answer, the question probably needs an exchange. Don't grind through dozens of pages.
- Quote the other area's pages with the `area:` prefix (`[[research:findings/f-...]]`). Resolution is global, so a bare `[[id]]` resolves too — but the prefix makes the cross-area source explicit, and if the citation later lands in one of your kb pages, Rule 2 validates the prefix against the target's actual area.
- Be honest about uncertainty. "Their kb has a finding suggesting X but no decision either way" is more useful than synthesizing a confident answer from partial reads.
- This skill is **read-only**. It writes nothing. If you find yourself writing files during `/answer-from-kb`, you're probably doing `/exchange` or `/implement` instead.
- The other area's pages can be at any status. A page marked `superseded` should not be cited as current; check `superseded_by` and cite the replacement instead.
- Lint rule 16 (configurable warning, off by default) tracks how often each role reads into other areas' kb bodies. If it gets noisy for a role, that's a signal to file more exchanges and do fewer direct reads.
