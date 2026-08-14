# Frontmatter Specification

Every markdown file in `kb/` directories and every data manifest carries YAML frontmatter. This document is the canonical reference.

## Frontmatter discipline

Frontmatter is written at file creation and updated whenever the page's content materially changes. The flow depends on the creation path:

- **`/ingest`** — produces a `source` page with full frontmatter (provenance pointing into `raw/`, retrieved date, summary).
- **`/ask`** synthesis — when a query produces a novel answer worth preserving, the agent files a new `finding` (or `concept` if not yet established) with summary, evidence list pointing to source pages used, and area set to the current role's area.
- **In-conversation work** — when the user and agent develop an idea or hypothesis, the agent files a `concept` page starting at status `seed` or `developing`, with minimal frontmatter (id, type, status, summary, area, relevant_to).
- **`/wrap-up` compaction** — entries in `_journal/pulse.log` flagged `→ to be filed: ...` are materialized into kb pages during compaction. Frontmatter is derived from the log entry plus the area context.
- **`/replan`** — if a replan produces a new decision worth recording independently of the spec, the skill spawns a `decision` page.
- **`/promote`** — promotion updates frontmatter (type and area transitions, plus `human_reviewed: false` and `promoted_from`/`promoted_on` for commons promotions). Other frontmatter fields are preserved.

When updating an existing page:

- Always bump `updated` to the current date when the body changes substantively.
- Update `status` when the page's epistemic position has shifted (concept stage moves, finding becomes archived, decision is superseded).
- Update type-specific fields (`evidence`, `confidence`, `superseded_by`) as new information arrives.
- Never change `type` by hand-editing — use `/promote` for type transitions.
- Never change `id` once a page is created — IDs are stable references.

Required-at-creation fields (per type) are enforced by lint Rule 6. Status transitions that leave required fields empty are also caught by lint.

## Required fields on all kb pages

```yaml
---
id: f-2026-05-shot-noise-1310nm        # stable; <type-prefix>-<date>-<slug>
title: Shot noise floor at 1310nm photodetector
type: finding                           # source | concept | finding | decision
status: active                          # see type-specific lifecycles below
area: research/optics                   # path; "commons" for shared
created: 2026-05-04
updated: 2026-05-04
summary: At 1310nm with 1mA photocurrent, shot noise dominates above ~10kHz.
relevant_to:                            # topical hints; omit for commons pages
  - photodetector design
  - noise budget
  - 1310nm wavelength
---
```

### ID prefixes by type

- `s-` — source
- `c-` — concept
- `f-` — finding
- `d-` — decision

### `area`

For `commons/kb/` pages, set `area: commons`. For area pages, use the path under `areas/` (e.g., `research`, `research/optics`, `business-model`).

### `relevant_to`

Topical hints used by agents to decide whether a page is worth loading into context. Omit for `commons/kb/` pages — commons is by definition relevant to everyone.

### `summary`

One sentence (≤25 words). The "index card" version of the page. Agents read this before deciding whether to load the body.

### `when_to_load` (optional)

Task-conditional guidance on whether to load the page body. **Optional.** Where `summary` describes *what the page contains*, `when_to_load` tells the agent *whether a given task makes the body worth the token cost*.

The field exists because `summary` + `relevant_to` answer "is this page about the right topic?" but not "is this page the right artifact for this task?" — two different questions. A page can be on-topic but useless for the current work (the topic is covered better in a cheaper alternative; the page assumes context the current task doesn't share; the page is a synthesis when the task needs primary text). `when_to_load` is the place to surface that.

Format: 1–3 sentences. Lean toward describing the **negative space** — when *not* to load — because the default is "open it" once a wikilink exists. The field's job is to suggest "don't bother."

Good `when_to_load` values share three properties:

1. **Task-conditional, not content-descriptive.** "Read when evaluating a specific Reg D or Reg A+ offering" — describes the reader's task. Bad: "Read when interested in private-placement DD" — that's just `relevant_to` restated.
2. **Comparative.** Names a cheaper or differently-shaped alternative where applicable. "The underlying findings cover the regulatory mechanics; load this only when you need the playbook spine."
3. **Specific about what's NOT in the page.** "Doesn't include foreign-asset overlay; for that, load [[f-...-foreign-project-risk-sub-taxonomy]] separately."

Examples:

For a decision page:
```yaml
when_to_load: |
  Read when evaluating a specific Reg D or Reg A+ offering. Skip for general
  questions about US securities law — the underlying findings cover those.
```

For a synthesis finding cited by a downstream playbook:
```yaml
when_to_load: |
  Read when building or refining DD process structure. The recommendations
  are organized by phase; cite specific rows from the playbook rather than
  re-deriving. Skip if you need only a single recommendation.
```

For a source page:
```yaml
when_to_load: |
  Read when you need primary-source language — quotes, audit-trail of which
  enforcement events are cited. Skip if a derivative finding already cites
  the specific item you need.
```

For an under_test concept:
```yaml
when_to_load: |
  Read when designing process discipline or evaluating whether to adopt
  investor-side DD documentation. The concept is unresolved; reading it
  surfaces the open question, not an answer.
```

Skip the field when there's no useful "don't load" signal — for short pages where loading is always cheap, for pages whose value is hard to scope task-conditionally, or for sources whose only purpose is to be cited verbatim. Missing `when_to_load` falls back on `summary` + `relevant_to`, which is fine.

## Type-specific fields

### `source`

```yaml
type: source
provenance:
  kind: external                        # external | internal-experiment | internal-notes
  title: Saleh & Teich, Photonics, ch 17
  author: Saleh, B.E.A.; Teich, M.C.
  url: ...                              # if external and web-accessible
  retrieved: 2026-04-12
  raw_path: raw/papers/saleh-teich-ch17.pdf
```

Lifecycle: `active` | `archived` | `superseded`.

The body of a source page is the structured summary of the raw material — key points, claims worth tracking, methods used, caveats. This summary is what agents cite when building concepts and findings; they don't re-read the raw PDF every time. Direct quotes (with location) may be used sparingly when exact wording matters.

### `concept`

```yaml
type: concept
status: under_test                      # see lifecycle below
evidence:                               # required if status is under_test or later
  - [[experiments/2026-04-photodetector-noise]]
  - [[sources/saleh-teich-ch17]]
confidence: medium                      # low | medium | high
```

Lifecycle:

- `seed` — initial spark; phrase as "one direction is..."
- `developing` — informal idea; phrase as "the working idea is..."
- `under_test` — formal claim with evidence being gathered.
- `supported` — sufficient evidence; ready for promotion to finding.
- `falsified` — disproven; anti-repetition memory.
- `dropped` — abandoned without resolution.
- `superseded` — replaced; follow `superseded_by`.

#### Body shape for `under_test` and later

When a concept reaches `under_test`, the body should make the test legible. A useful pattern — not a required form — is to cover, in roughly this order:

- **What we're testing** — the claim, stated precisely enough that a reader can recognize evidence for or against it.
- **Why this is a concept, not a finding** — the gap that keeps it from being established (single-source, source-asymmetry, interested-party reliance, etc.). Make the gap concrete so a reader can validate it.
- **Why the idea is worth tracking** — second-order rationales that justify the cost of carrying an unresolved hypothesis.
- **How to test it** — at minimum an *observable* (what evidence would bear on the claim) and a *disconfirmer* (what would falsify it). Without these two, the concept will drift in `under_test` indefinitely.
- **Promotion criteria** — what specifically would move this to `supported`. Name the kind of evidence or source that would close the gap.
- **If falsified** — what specifically would move this to `falsified`, and what artifacts (decision pages, playbooks) would need updating if so.

The point isn't form-filling. The point is that an `under_test` concept without an articulated test and a falsification condition is indistinguishable from a `developing` one — and the framework has no way to recover its status without re-reading the originating conversation. Concepts at `seed` or `developing` don't need this structure; one paragraph is fine.

### `finding`

```yaml
type: finding
provenance:
  kind: concept                         # concept | external | experiment
  ref: [[concepts/c-2026-04-shot-noise]]
  raw_path: ~                           # populated if finding derives directly from raw material
evidence:
  - [[experiments/2026-04-photodetector-noise]]
confidence: high
superseded_by: ~
```

Lifecycle: `active` | `archived` | `superseded`.

A finding's provenance points back to the concept it was promoted from (`kind: concept`) or to an external source if it came in already-established (`kind: external`, with `raw_path` populated).

### `decision`

```yaml
type: decision
alternatives_considered:
  - [[concepts/c-2026-04-balanced-detection]]
  - [[concepts/c-2026-04-lower-bias]]
rationale_summary: ...
superseded_by: ~
```

Lifecycle: `active` | `superseded`.

## Commons-promoted items

Pages promoted into `commons/kb/` carry three additional fields:

```yaml
human_reviewed: false                   # flipped to true when human acks
promoted_from: areas/research/optics
promoted_on: 2026-05-08
```

## POR files

`POR.md` files (when the `por` capability is enabled) use a simpler frontmatter:

```yaml
---
type: por
area: research/optics
phase: detector characterization (2 of 4)
last_updated: 2026-05-08
---
```

## Wikilinks in frontmatter

Several fields carry `[[wikilinks]]` — `evidence`, `provenance.ref`, `alternatives_considered`, `superseded_by`. Lint Rule 2 validates these exactly like body links (resolution and area prefix). Authoring them **unquoted** (`evidence:\n  - [[sources/s-…]]`) is fine — the framework quotes them on read so YAML doesn't mis-parse `[[x]]` as a nested sequence. Tools that re-serialize frontmatter (e.g. `promote.py`) emit them **quoted** (`"[[sources/s-…]]"`); both forms resolve.

## Lint-maintained, not author-written

The fields `links_in` and `links_out` are not written into the frontmatter directly. The linter maintains them in a sidecar `<page>.links.json` so they don't clutter the human-edited file. The sidecar is git-ignored.

## Field ordering convention

For readability, frontmatter fields appear in this order:

1. `id`
2. `title`
3. `type`
4. `status`
5. `area`
6. `created`, `updated`
7. `summary`
8. `relevant_to`
9. Type-specific fields (`provenance`, `evidence`, `confidence`, `alternatives_considered`, etc.)
10. Commons-promotion fields (`human_reviewed`, `promoted_from`, `promoted_on`) if present
11. `superseded_by` if present

Lint does not enforce ordering, but agents writing new pages should follow it.
