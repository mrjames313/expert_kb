# Promotion Protocol

How content moves from an area's `kb/` into `commons/kb/`. The always-on protection: any change to `commons/` goes through `commons/_proposed/` first, with a human gate before promotion.

When `formal_review` is enabled, the protocol adds per-area reviewer subagents that produce structured verdicts.

## Filing a proposal

An agent in area X creates content believed to be project-wide and invokes `/propose-promotion <page>`. The skill:

1. Copies the page to `commons/_proposed/<date>-<slug>/page.md`.
2. Generates `proposal.md` with:
   - Rationale (why this is project-wide).
   - Summary of the proposed page's content.
   - Proposing role and area.
3. Writes an INBOX entry under "Heads up": "Proposal awaiting reviews from: [list of areas]."

When `formal_review` is off, that's all — the human reads the proposal directly (often in conversation, or via INBOX) and decides.

When `formal_review` is on, the proposal stays in `_proposed/` until each other area has filed a verdict (see below).

## Review (formal_review only)

For each other area, `/review-promotion <proposal>` is invoked. The skill spawns a subagent with that area's reviewer role context. The subagent writes `verdict-<area>.md`:

```yaml
---
verdict: APPROVE              # APPROVE | OBJECT | ABSTAIN
reviewer_area: business-model
reviewer_role: business-analyst
reviewed_on: 2026-05-09
---

# Rationale

(1–3 paragraphs)

# Concerns

(required if verdict is OBJECT)
```

`ABSTAIN` means "this doesn't materially affect our work" — does not block consensus.

## Consensus rules (formal_review only)

Once all other areas have weighed in:

- **All non-abstain verdicts are APPROVE** → auto-promote.
- **Any OBJECT** → escalate to human via INBOX "Needs decision"; stays pending until you resolve.
- **All ABSTAIN** → human decides whether the page should be commons at all.

## Promotion

The `/promote` skill (auto-invoked on consensus when `formal_review` is on; manually invoked otherwise after human approval) does:

1. Generate a new commons id using the `<prefix>-commons-<slug>` convention (source date dropped). E.g., `f-2026-05-shot-noise` → `f-commons-shot-noise`. This is the same convention used by the commons-extension pathway (see `commons-extension-protocol.md`), so both pathways produce consistent ids in commons.
2. Move `_proposed/<slug>/page.md` to `commons/kb/<type>/<new-commons-id>.md`.
3. Set frontmatter:
   - `id: <new-commons-id>` (the page's new id, not the source's)
   - `human_reviewed: false` (proposal-pathway pages need a reviewer's ack; this is the meaningful difference from commons-extension's `human_reviewed: true` which means user confirmed inline)
   - `promoted_from_page: <source-id>` (the original area page id, for audit trail)
   - `promoted_from_area: areas/<x>`
   - `promoted_on: <date>`
   - `promotion_path: proposal-and-promote` (distinguishes from `commons-extension` so the two pathways are auditable separately)
4. Leave the source area page completely unchanged. Per the source area's `/propose-promotion` discipline, the area copy stays in place; the new commons page coexists with it under a distinct id. Do **not** mark the source `superseded` — superseding is for a page that has been *replaced*, and linking to a superseded page is a lint error (see `link-conventions.md`), so it would turn every inbound citation to the area page into an error.
5. Write a `CHANGELOG.md` entry (citing the new commons id).
6. File an INBOX entry under "Awaiting your ack": "Promoted [[finding]] — awaiting human review."

Lint Rule 18 enforces project-wide id uniqueness, so a faulty implementation that retained the source id would fail lint immediately.

## Human acknowledgment

The human reviews promoted commons pages (often in batch via INBOX) and flips `human_reviewed: true`.

Lint Rule 10 surfaces unreviewed promotions aged past `promotion_freshness_active_days` (default 14) under "Needs decision" in INBOX.

## Audit trail

The `_proposed/` directory and its verdict files (when applicable) are kept after promotion. They're the audit trail for "why is this in commons?"

## Objection resolution

When you're called in to resolve an objection:

- **Adopt the objection** — proposal modified or withdrawn.
- **Overrule it** — proposal promoted as-is with a note explaining.
- **Split** — some content promotes; some returns to the area as not-yet-commons.

## Promotion within an area's lifecycle

Promotion from `concept` (status: `supported`) to `finding` within the same area uses the same machinery, scoped to the area. The proposal lives in the area's own `_proposed/` directory (if needed) or is simply executed via `/promote` after human approval. Per-area reviewer subagents only fire for promotions targeting commons.
