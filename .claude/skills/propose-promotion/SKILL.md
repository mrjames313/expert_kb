---
name: propose-promotion
description: Propose a finding, decision, or concept from an area's kb for promotion to commons (project-wide knowledge). Creates a proposal directory but does not move the page — that's /promote.
---

# /propose-promotion

Stages a page for promotion to `commons/kb/` by creating a proposal directory. The actual move happens later via `/promote` (typically by the coordinator or after human review).

## When to use

- A finding, decision, or concept in the role's area has become broadly relevant: other areas would benefit from citing it, or it's a project-wide assumption.
- The page has settled (concept is `supported`, finding is `active` and stable, decision is `active`).

Don't propose for promotion:
- Pages still under iteration (`under_test` concepts, drafts).
- Pages that are only relevant to one area (those stay in the area's kb).
- Pages that are superseded, falsified, or dropped.

## Steps

1. **Identify the page.** Confirm with the user which page in the role's area is being proposed. Read it and verify:
   - It has a settled status (concept `supported`, finding `active`, decision `active`).
   - Its claims are well-cited from sources in raw/.
   - It would actually be useful to other areas (not just your own).

2. **Pick a proposal slug.** Use `YYYY-MM-<short-name>` (e.g. `2026-05-shot-noise-floor`). The slug becomes the directory name under `commons/_proposed/`.

3. **Create the proposal directory.** Under `commons/_proposed/<slug>/`:
   - `page.md` — exact copy of the area kb page, including its current frontmatter. `/promote` will update the frontmatter on acceptance.
   - `proposal.md` — proposal metadata:
     ```yaml
     ---
     proposing_area: <your-area>
     proposed_on: 2026-05-15
     proposed_by: <role>
     ---

     # Proposal: promote <page-id>

     ## Why commons

     2–4 sentences on why this needs to be project-wide rather than area-local.

     ## Affected areas

     List other areas that would benefit from citing this. If `multi_area` is on,
     each affected area is expected to file a verdict file.
     ```

4. **If `multi_area` is enabled**: notify other affected areas *without writing into their paths* — file an INBOX "Heads up" entry pointing at `commons/_proposed/<slug>/`, and/or open an `/exchange` if the review needs a real back-and-forth. (Do **not** append to another area's `_journal/pulse.log`; path ownership forbids writing into areas you don't own.) Each area's role can then add a verdict file to `commons/_proposed/<slug>/verdict-<area>.md` with APPROVE / OBJECT / ABSTAIN. (See `_framework/schema/promotion-protocol.md` for the full protocol.)

5. **Record in pulse.log.**
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Proposed <page-id> for promotion to commons.
   → to be filed: decisions/d-YYYY-MM-DD-propose-<slug>
   ```
   Create a corresponding decision page that documents the rationale.

6. **Verify.** Run `python _framework/tools/lint.py`. The proposal directory's `page.md` should be lint-clean (it's just a copy of an already-lint-clean page).

7. **Brief the user.** Tell them the proposal is staged and what happens next:
   - Other affected areas (if any) will file verdicts.
   - The coordinator (or a human) runs `/promote <slug>` to accept.

## Notes

- The original page stays in the area's kb. Promotion *copies* and *updates*; it doesn't move the area copy. After promotion, the area copy can either be marked `superseded` with `superseded_by` pointing at the commons version, or kept as-is if the area still needs an area-specific framing.
- Don't propose for promotion something that's actually two ideas. Split it first in the area kb, then propose the canonical one.
- A proposal can sit in `commons/_proposed/` indefinitely. Stale proposals are surfaced by lint rule 10 (configurable warning, off by default).
