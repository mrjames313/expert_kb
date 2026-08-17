---
name: promote
description: Accept a proposal from commons/_proposed/<slug>/ and move the page into commons/kb/. Updates frontmatter, writes a CHANGELOG entry, and leaves an audit trail.
---

# /promote

Accepts a staged proposal and moves the page into `commons/kb/`. Typically run by the coordinator (when `por` is enabled) or by a human reviewer.

## When to use

- A proposal exists at `commons/_proposed/<slug>/` (created via `/propose-promotion`).
- The proposal has been reviewed:
  - With `formal_review` enabled: each affected area has filed a verdict file (via `/review-promotion`), and there are no `OBJECT` verdicts.
  - Without `formal_review`: a human has confirmed the proposal should land.

## Steps

1. **Verify the proposal is acceptable.** Read every file in `commons/_proposed/<slug>/`:
   - `proposal.md` — confirm the rationale.
   - `page.md` — confirm the page is lint-clean and at a settled status.
   - Any `verdict-<area>.md` files (present only when `formal_review` is on) — if any has verdict `OBJECT`, surface that to the user and stop. The objecting area must approve (or change to ABSTAIN) before promotion can proceed.

2. **Run the promote tool.**
   ```
   python _framework/tools/promote.py <slug>
   ```
   The tool:
   - Moves `commons/_proposed/<slug>/page.md` → `commons/kb/<type>/<id>.md`.
   - Updates frontmatter: `id` (new `<prefix>-commons-<slug>`), `area: commons`, `human_reviewed: false`, `promoted_from_page: <source-id>`, `promoted_from_area: areas/<x>`, `promoted_on: <today>`, `promotion_path: proposal-and-promote`, `aligned_on: <today>`, `updated: <today>` (drops `relevant_to`).
   - Adds a `commons_twin` back-pointer to the source area page (the one sanctioned cross-area metadata write). If it warns the source wasn't found, note it.
   - Prepends a CHANGELOG entry to `commons/CHANGELOG.md`.
   - Leaves `proposal.md` and verdict files in `commons/_proposed/<slug>/` as audit trail.

3. **Edit the new commons page for a commons reader.** The staged copy is verbatim — clean it, but don't summarize; keep every protocol, number, and caveat.
   - **Strip resolved-deliberation cruft** — resolved-question sections, superseded sections, closed "left open" lists. This content misleads a cold reader.
   - **Rewrite conceptual links to their commons twins** (leave provenance links to area sources), reviewing before applying:
     ```
     python _framework/tools/commons_links.py rewrite commons/kb/<type>/<new-id>.md           # review proposed changes
     python _framework/tools/commons_links.py rewrite commons/kb/<type>/<new-id>.md --apply    # then apply
     ```

4. **Leave the source area page's content in place.** Do **not** modify it beyond the `commons_twin` back-pointer the tool just added. The commons page is a *coexisting copy* for a project-wide audience, not a replacement — it lands under a distinct id, and existing `[[...]]` citations to the area page keep resolving. Do **not** mark the area copy `superseded`: linking to a superseded page is a lint error, so it would convert every inbound citation into an error in one step.

5. **Verify.** Run `python _framework/tools/lint.py`. The promoted page should be lint-clean, and the source area page stays clean too.

6. **Record in pulse.log.** In whichever pulse log is most appropriate (the coordinator's commons pulse, or the proposing area's pulse):
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Promoted <page-id> to commons (from <proposing-area>).
   ```

7. **Brief the user.** Confirm what was promoted, the new commons id, whether the source twin back-pointer was set, and that the "Awaiting your ack" INBOX entry was filed. `promote.py` files that INBOX entry itself (promotion-protocol.md step 7) — you don't write it by hand; if its output warns the entry wasn't filed (no `## Awaiting your ack` section in INBOX.md), surface that.

## Notes

- `promote.py` refuses to overwrite an existing file. If the target id already exists in commons, surface that — either the proposal duplicates an existing commons page (close the proposal as redundant) or the page needs a different id.
- The promoted page lands with `human_reviewed: false`. A human can later flip this to `true` after they've reviewed; until then, lint rule 10 (a configurable warning) can surface unverified commons pages.
- The audit trail in `commons/_proposed/<slug>/` is deliberately retained. Don't delete it; it's the record of who proposed what, when, and why.
- After promotion, the source area page is unchanged, so existing `[[...]]` citations to it keep working. The commons page has a distinct id; repoint a citation at the commons id only where a canonical project-wide reference is wanted — a per-link judgment, not a blanket rewrite.
- Promotion does not pull dependent pages along with it. If the page references `[[c-foo-thing]]` and `c-foo-thing` is also area-local, you may need to promote that one too. Lint rule 9 (configurable warning) can surface unresolved cross-area citations in commons pages.
