## Cross-area reads

When `multi_area` is enabled, prefer `/exchange` over deep-reading another area's kb pages.

- Reading another area's `kb/index.md` or page frontmatter is fine for orientation.
- Deep reads (full bodies) of another area's pages should be exceptional and justified in your task notes.
- When you have a real question for another area's expertise, file a query: `/exchange <other-area> <question>` (kind `query`, the default). The other area's agents will answer from their kb authoritatively.
- When you've concluded something another area's role needs but wouldn't know to ask for, push it: `/exchange <other-area> <statement> --kind brief`. A brief has no responder obligation; its targeted roles dispose of it (preload / file / cite).
- Read-only queries about another area's state ("what's in engineering's pulse?") do not require a role switch — stay in your role and read what's needed to answer.
- Cite cross-area pages with an area prefix: `[[engineering:findings/f-…]]`.

Exchanges are kept indefinitely after closing — they're often the best institutional record of "why does X area think Y about Z."
