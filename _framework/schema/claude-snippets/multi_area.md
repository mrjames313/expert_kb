## Cross-area reads

When `multi_area` is enabled, cross-area *reads* are acceptable — occasional use is fine — but *writes* into another area are not, and iterative needs belong in an exchange.

- Reading another area's `kb/index.md`, page frontmatter, or an occasional full page is fine. Stay in your role; no role switch needed.
- If you find yourself reading into another area *repeatedly*, that's the signal to file an exchange instead of continuing to read.
- **Never write** into another area's kb or role files. The one exception is the `commons_twin` back-pointer set during promotion (framework-maintained metadata).
- File a **query** when you need another area's expertise: `/exchange <other-area> <question>` (kind `query`, the default). Their role answers authoritatively.
- File a **brief** when you've concluded something a role in another area needs but wouldn't know to ask for: `/exchange <other-area> <statement> --kind brief` (no responder obligation; targeted roles dispose via preload / file / cite).
- Cite cross-area pages with an area prefix: `[[engineering:findings/f-…]]`.

Exchanges are kept indefinitely after closing — they're often the best institutional record of "why does X area think Y about Z."
