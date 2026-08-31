# Link Conventions

How links work in the knowledge base, and how the linter maintains them.

## Wikilinks for kb cross-references

Within `kb/` directories, agents use Obsidian-style wikilinks:

```
This builds on [[concepts/c-2026-04-shot-noise]] and contradicts
[[findings/f-2026-03-noise-model]].
```

Wikilink targets are resolved by the linter — it walks the kb tree and matches the path. Targets do not need the `.md` extension.

### Area prefixes on cross-area links

A wikilink target may carry an `area:` prefix naming where the target lives — `[[engineering:findings/f-...]]`, `[[commons:decisions/d-...]]`, or a nested `[[research/optics:concepts/c-...]]`. The split is on the first colon, so slashes in a nested prefix or in the target are fine.

The prefix is a **readability** aid — resolution still works without it, since ids are project-unique (Rule 18). But when a prefix *is* present, the linter checks it against the target's actual area and **errors on a mismatch** (Rule 2). Keep same-area links bare; add the prefix when you link into another area or commons, so the reader sees the boundary being crossed.

## Markdown links for everything else

For files outside `kb/` (code, manifests, specs, raw materials, exchange files), use relative markdown links with explicit paths. Only `kb/` pages are in the wikilink index, so a `[[wikilink]]` to any of these can never resolve — a data manifest is the easy one to get wrong, since it carries kb-style frontmatter but does not live in `kb/`. Rule 2 resolves relative links too, so both forms are checked:

```
See the measurement procedure at
[experiments/2026-04/procedure.md](../../specs/2026-04-noise-floor/procedure.md).
```

## Forward links and backlinks

**Forward links** are written by the authoring agent — they appear in the body of the page.

**Backlinks** are maintained by the linter. For each page, the linter generates a sidecar file `<page>.links.json` containing:

```json
{
  "links_in": ["concepts/c-2026-04-shot-noise.md", "..."],
  "links_out": ["sources/saleh-teich-ch17.md", "..."]
}
```

Sidecars are git-ignored. They're regenerated on every `/check` or `/wrap-up` invocation. Authors never edit them.

## Bidirectionality is enforced by lint

If page A links to page B, B's sidecar will list A in `links_in`. This is automatic — the linter regenerates sidecars rather than failing if they're out of sync.

Broken links (forward references to non-existent pages) are lint errors.

Orphan pages (no inbound links) are flagged as warnings — they may indicate isolated content, or they may simply be index-page leaves.

## Superseded pages

A page with `status: superseded` must have `superseded_by` populated, pointing to the replacement.

**Linking to a superseded page is an error**, not a warning. The linter suggests the replacement in its error output.

When you discover a forward link points to a now-superseded page, follow `superseded_by` and update your link to point at the current version.

## Cross-area links

Cross-area links are valid but watched. Prefix them with the target's area (see "Area prefixes" above). Lint warns when a single page accumulates links to 3 or more distinct areas — it may indicate that the topic belongs in commons (via promotion) or in an exchange (when `multi_area` is enabled).

Pages with `area: commons` are exempt from this rule — commons is by definition relevant to everyone.

## Bidirectional content consistency

The linter ensures *link structure* stays consistent. **Content consistency** — keeping the assertions of linked pages aligned — requires both lint and convention:

**Lint (Rule 13)** flags pages whose `links_out` targets were updated more recently than the page itself. These are candidates for content-consistency review.

**Convention** (in `CLAUDE.md`): after substantively updating a page, agents check the page's backlinks. For each backlinker, the agent decides whether the update affects the backlinker's content. If yes:
- Update the backlinker inline (preferred for small changes).
- Or file a "Heads up" entry in INBOX naming the affected pages (for larger changes you don't want to make immediately).

The two mechanisms catch different failure modes: convention catches semantic dependency the linter can't see; lint catches cases where the convention was missed.
