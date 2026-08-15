---
name: amend-commons
description: Edit an existing commons page in place — fix an error, rewrite links to commons twins, or reconcile drift with its area source. Light-gated: human confirms in conversation and the change is logged to the CHANGELOG.
---

# /amend-commons

The sanctioned way to change an **existing** commons page. Commons is otherwise proposals-only, so direct edits go through here — with a light gate (human confirmation + a `CHANGELOG.md` entry) rather than a full proposal, since a correction is lower-stakes than a promotion.

Any role may invoke it (commons is jointly stewarded). Use it for corrections, link rewrites, and drift reconciliation — **not** for creating new commons pages (`/propose-promotion` → `/promote`) or for editing area pages (edit those directly).

## When to use

- A commons page has an error found after promotion.
- Lint's staleness rule flags a commons page as behind its area source → reconcile it.
- Lint's twin-preference rule flags a commons page citing an area page that has a commons twin → rewrite the link.
- Any other in-place correction to an existing commons page.

## Steps

1. **Find the page and confirm it's commons.** Read it; verify `area: commons`. Note its `promoted_from_page` (the area source) and `aligned_on`.

2. **Determine the change.** One of:
   - **Correction** — a factual/typo fix.
   - **Link rewrite** — preview and apply with the shared tool (propose-for-review):
     ```
     python _framework/tools/commons_links.py rewrite commons/kb/<type>/<id>.md          # dry run
     python _framework/tools/commons_links.py rewrite commons/kb/<type>/<id>.md --apply   # after you confirm
     ```
     Show the proposed `[[old]] → [[new]]` list; it preserves aliases and skips code fences.
   - **Drift reconciliation** — re-read the area source (`promoted_from_page`), bring the substantive content back into line (re-applying the commons-audience edits: keep protocols/numbers/caveats verbatim, strip resolved-deliberation cruft), then in step 4 bump `aligned_on`.

3. **Confirm with the human (light gate).** Show the diff (or the rewrite list) and get approval in conversation before writing. Don't write commons without it.

4. **Apply the edit.** Write the commons page. Update `updated`. If this was a drift reconciliation, set `aligned_on` to today.

5. **Propagate to the area twin if the fix belongs there too.** If the correction also applies to the area source (e.g., a factual error present in both):
   - If you own that area, fix it there directly.
   - Otherwise **do not write the area page** — file an INBOX "Heads up" for its owner:
     > **Twin heads-up**: `commons/kb/.../<commons-id>` was corrected; its source `[[<source-id>]]` in `areas/<area>/` likely needs the same fix: <one line>.

6. **Log to the CHANGELOG.** Prepend to `commons/CHANGELOG.md`:
   ```
   ## <YYYY-MM-DD> — amended <commons-id>
   <one line: what changed and why>
   ```

7. **Verify.** Run `python _framework/tools/lint.py`. Rule 2 confirms links (body + frontmatter) still resolve; the staleness/twin-preference warnings should clear for this page.

8. **Brief the user.** Summarize the change, and whether an area twin heads-up was filed.

## Notes

- **This is the only sanctioned way to edit an existing commons page directly.** Don't hand-edit commons outside it — the light gate + CHANGELOG are the audit trail that makes direct commons writes acceptable.
- **Reverse propagation is a heads-up, not a write.** You never write another area's pages; the area's owner applies the twin fix (unless you own that area).
- **Alignment is asymmetric.** `aligned_on` lives only on the commons page. Area→commons drift is caught by lint; commons→area is handled by the heads-up above.
- Not for supersession or deletion — a superseded/removed commons page is a separate, human decision.
