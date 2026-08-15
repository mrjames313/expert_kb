---
name: add-area
description: Create a new area scaffold under areas/<name>/ with brief.md, pulse.md, kb subdirectories, and at least one role. Updates areas-index.md on the next lint run.
---

# /add-area

Creates a new area scaffold under `areas/<name>/`. An area is the framework's primary unit of specialization — each area has its own kb, roles, raw materials, specs, and (optionally) code/data.

## When to use

- The user wants to organize a new specialty or workstream that doesn't fit into existing areas.
- Cross-area work has become heavy enough that the new domain deserves its own area.
- A `/plan` or `/implement` revealed that some work belongs in an area that doesn't exist yet.

Don't add an area for:
- Single one-off tasks (use a spec in an existing area).
- A topic that overlaps heavily with an existing area (extend that area instead).

## Steps

1. **Confirm the area name and shape.** Ask the user:
   - **Name** — a short slug (e.g. `optics`, `business-model`, `frontend`). Will become the directory name and the `area:` value in frontmatter.
   - **Sub-area or top-level?** If sub-area, where does it nest (e.g. `research/optics`)?
   - **Initial role(s)** — at least one. Common pattern: one implementer role (`researcher`, `engineer`, `designer`) per area.
   - **Brief content** — 2–4 sentences on the area's purpose. Save asking for this until last; the user often firms up the brief as they answer the other questions.

2. **Create the directory structure.** Under `areas/<area-path>/`:
   ```
   brief.md              — area description
   pulse.md              — current focus, recent decisions, etc. (template)
   _journal/
     pulse.log           — empty
   kb/
     sources/
     concepts/
     findings/
     decisions/
   specs/                — empty (specs created via /plan)
   code/                 — empty (created as needed by /implement)
   data/
     manifests/          — empty
   raw/                  — empty (populated by /ingest)
   roles/
     <role-name>/
       role.md           — initial role file
   ```

   Use the templates in `_framework/schema/`:
   - `frontmatter.md` and `role-template.md` for the role file structure.
   - The existing `commons/brief.md` and `commons/pulse.md` as references for those files' structure.

3. **Populate `brief.md`** with the user's description. Frontmatter is not required for `brief.md` — it's a free-form document.

4. **Populate `pulse.md`** with a starter template:
   ```markdown
   # <area> — pulse

   _Initialized: YYYY-MM-DD_

   ## Current focus

   _(set when work begins)_

   ## Recent decisions (last 7 active days)

   _None yet._

   ## Active concepts under test

   _None yet._

   ## Open questions

   _None yet._

   ## Recent findings (last 5)

   _None yet._
   ```

5. **Create at least one role file** under `areas/<area-path>/roles/<role-name>/role.md`. Use the template at `_framework/schema/role-template.md`. Adjust:
   - Frontmatter: `role`, `area`, `summary`.
   - "Preload context (full)" — start with CLAUDE.md, schema docs, the new area's brief and pulse, and `areas-index.md`. Keep it minimal initially; expand as needed.
   - "Preload context (frontmatter only)" — patterns like `/areas/<area-path>/kb/` to surface area kb pages.
   - "Operating boundaries" — `Writes allowed: /areas/<area-path>/** except /areas/<area-path>/raw/**`.
   - "Allowed skills" — at minimum `start, ingest, ask, plan, implement, replan, wrap-up, check`. Add capability-conditional skills via `/framework enable`.

6. **If `por` is enabled**: also create `areas/<area-path>/POR.md` (use the template the `por` capability generates — see `_framework/tools/framework.py` `_plan_por` or just copy `commons/POR.md` structure). Without this step, lint won't fail but the role won't have a POR to load.

7. **Verify.** Run:
   ```
   python _framework/tools/lint.py
   ```
   Lint regenerates `areas-index.md` on this run, so the new area appears there automatically. The new role file should be lint-clean (frontmatter complete; no broken wikilinks).

8. **Record in pulse.log.** Append to `commons/_journal/pulse.log`:
   ```
   ## [YYYY-MM-DD HH:MM] decision <role>
   Created new area: <area-path>. Initial role: <role-name>.
   → to be filed: decisions/d-YYYY-MM-DD-add-area-<slug>
   ```
   Create the corresponding decision page documenting why the area was created and what scope it covers.

9. **Commons extension review (default on).** Skip this step if the user passed `--no-extend-commons` to `/add-area`, OR if this is the project's first area (commons-extension is a no-op when there's nothing to extend from). Otherwise:

   The point: when a new area is added, kb pages in existing areas may become more useful in commons (visible to all areas) than they were in their original area. Catch those moments instead of leaving them for later.

   Workflow:

   a. **Enumerate candidates.** Run:
      ```
      python _framework/tools/commons_extension.py list --new-area <new-area-name>
      ```
      The tool returns structured JSON with `context` (project framing) and `candidates` (kb pages eligible for extension — findings, decisions, concepts; not sources; not statuses superseded/falsified/dropped/archived).

   b. **Display the context.** Show the project framing before the per-candidate review:
      ```
      The project now has N areas; commons holds M pages. Commons-extension on
      the project's 2nd area typically surfaces the most candidates — later
      area additions should usually find less to extend. K candidates surfaced.
      ```
      This calibrates the user's expectations for how many candidates to expect.

   c. **Filter candidates by semantic relevance.** For each candidate the tool returned, read its `summary`, `when_to_load` (if present), and `relevant_to` tags. Compare against the new area's brief. Surface only candidates that would plausibly be useful to the new area. Skip candidates whose `when_to_load` makes clear they're scoped narrower than the new area's domain. Use judgment — not all returned candidates need to be presented to the user.

   d. **For each surfaced candidate, present and ask.** Display the candidate's metadata to the user:
      ```
      Candidate: <page-id>
      Currently: <source-path>
      Summary:   <summary>
      when_to_load: <verbatim, or "(none specified)" if absent>
      Why surfaced: <one-line rationale citing the brief signal that matched>

      Extend commons with this? [y/n/skip]
      ```
      `skip` means defer with no commitment; the page stays where it is.

   e. **For each `y` confirmation, decide refine-vs-copy.** Read the source page's body. Decide whether it's already in suitably general framing or if it needs refinement for commons (e.g., the body uses area-specific language that would read awkwardly when invoked by a different area). If the source is already general, copy as-is. If it needs refinement, rewrite the body for general framing — keeping the substantive content intact, only adjusting the language.

      Then apply:
      ```
      # Copy as-is:
      python _framework/tools/commons_extension.py apply \
          --source-id <page-id> \
          --new-area <new-area-name>

      # Or with refinement (write refined body to a temp file first):
      python _framework/tools/commons_extension.py apply \
          --source-id <page-id> \
          --new-area <new-area-name> \
          --refined-body-file /tmp/refined-body.md
      ```
      The tool creates the new commons page with id `<type-prefix>-commons-<slug>` (source date dropped), sets `aligned_on` on it, updates `commons/CHANGELOG.md`, and adds a `commons_twin` back-pointer to the source page (its only change to the source).

      Then edit the new commons page for a commons reader, as `/promote` does — strip resolved-deliberation cruft and rewrite conceptual links to their commons twins (leave provenance links), reviewing before applying:
      ```
      python _framework/tools/commons_links.py rewrite commons/kb/<type>/<new-id>.md           # review
      python _framework/tools/commons_links.py rewrite commons/kb/<type>/<new-id>.md --apply    # then apply
      ```

   f. **After all confirmed extensions, run lint.** Verify references still resolve (wikilinks pointing at the source ids continue to work because the source pages are still in place; the new commons pages have new ids).

   g. **Journal the extensions** in `commons/_journal/pulse.log`:
      ```
      ## [YYYY-MM-DD HH:MM] decision <role>
      Extended commons during /add-area <new-area-name>: <N> pages from <source-areas>.
      ```

   Source area pages keep their content; the only change is the `commons_twin` back-pointer the tool adds. Existing wikilinks elsewhere still resolve to the area versions; the commons pages' own conceptual links are rewritten to twins in step e. Repointing *other* pages' links to the commons versions remains a per-link judgment made later.

10. **Brief the user.** Tell them the area is ready and what to do next: `/start <role-name>` to adopt the new role, then `/plan` to scope the first piece of work. If commons extension created any new commons pages, mention them briefly.

## Notes

- **Sub-areas nest naturally.** `areas/research/optics/` is a sub-area of `areas/research/`. A role in `optics/` would typically preload both `/areas/research/brief.md` and `/areas/research/optics/brief.md` so it inherits parent context. Use `/areas/research/kb/` and `/areas/research/optics/kb/` together as frontmatter-only patterns.
- **Initial role files can be light.** Don't try to specify everything up front. The role file is meant to be revised as the area's work surface clarifies. `/framework prune` will surface stale entries later.
- **Roles can share preload entries**, but each role is independent. Don't try to "inherit" — duplicate the entries instead. The framework deliberately favors explicitness over reuse here.
- **For `multi_area` enabled projects**: the new area is automatically eligible for `/exchange` once `multi_area` is on. No further setup needed.
- **For `formal_review` enabled projects**: after creating implementer role(s), run `/framework disable formal_review && /framework enable formal_review` to regenerate the reviewer variants including the new role. (Or manually create a `<role-name>-reviewer/role.md` mirror.)
