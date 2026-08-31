# Requirement-clause audit

A one-time pass over every requirement-shaped clause in the pulled docs, resolving each to its
enforcer. Maintainer-only, like `future-work.md` and `maintaining.md`.

**Why this exists.** The most-repeated bug in this project is a documented behaviour with no
implementation: the clause reads as done, nothing catches a page that violates it, and so
`lint: clean` asserts nothing about it. Instances were found one at a time, by a human reading.
This is the systematic sweep. `maintaining.md` → "Every requirement clause needs an enforcer or
a backfill" is the discipline that keeps the list from re-growing; this file is the baseline it
starts from.

**Method.** Grepped `CLAUDE.md`, `_framework/spec.md`, `_framework/schema/*.md`, and
`.claude/skills/*/SKILL.md` for requirement language (`must`, `never`, `always`, `required`,
`is an error`, `forbidden`, `immutable`). 97 matching lines across ~4,000 lines in 30+ files;
roughly a third are definitions or descriptions rather than requirements, leaving ~65 real
clauses. Each was resolved against the code by reading the relevant rule module or tool.

**Audited at:** framework_version 2026-08-31. G1 resolved by rewording; C1, C2 and C3 fixed the
same day; G2 and G3 are planned in `future-work.md`; C4 and C5 were found while planning G2 and
remain open.

**How to keep it true.** Clause anchors below are quoted verbatim so a grep can verify the
clause still exists as written — an edited or deleted clause self-reports. Only genuinely *new*
requirement clauses need a fresh read, and those are bounded by the diff (see the release
definition-of-done in `maintaining.md`).

---

## Gaps — a clause asserts behaviour nothing enforces

This is the work queue. Ordered by consequence.

### G1. Path ownership is enforced by nothing — and the spec claims otherwise

**The false clause is explicit.** `spec.md:192`, closing the write-permission table:

> Lint enforces category boundaries.

It does not. No rule module reads that table, and nothing detects a write outside a role's
boundary. The originally-planned Rule 19 (maintenance-category violations) was slotted for
exactly this and remains unimplemented — it needs to distinguish agent from human writes, which
probably requires git author signals.

Every statement of the ownership model rests on agent obedience alone:

| Clause | Where |
|---|---|
| "`commons/` is jointly stewarded; direct writes are forbidden" | `CLAUDE.md:20` |
| "Never write directly to `commons/` — proposals only" | `CLAUDE.md:42` |
| "Writes to /commons/: forbidden; use /propose-promotion" | `spec.md:483`, `role-template.md:69` |
| "Writes to other areas: forbidden" | `spec.md:484`, `role-template.md:70` |
| the `H` / `A` / `L` write-permission table | `spec.md:176-191` |

This is the framework's central governance model, and it is the one thing in the corpus where a
normative doc makes an unqualified claim of mechanical enforcement that is simply untrue. Note
the model still *works* in practice — agents follow it — but a violation is silent, and the
`/propose-promotion` step-4 defect (an illegal cross-area `pulse.log` write) is a case where one
shipped and was caught by review, not by lint.

**Resolved 2026-08-31 by rewording, not by enforcement.** The decision was that ownership is a
guideline admitting reasonable exceptions, not a sealed boundary — so every site now says that
plainly: `CLAUDE.md:24`, `spec.md` (the table's closing paragraph), `role-template.md:69-70`,
the `multi_area` snippet, and `exchange`/`implement` SKILL.md. The routes stay the default and a
genuine exception is expected to be raised in conversation with a visible trace, rather than
written silently. `raw/` immutability is called out as the one mechanically-enforced member
(Rule 17), and the `L` rows as enforced-by-regeneration.

**Still open:** mechanical enforcement of the `A`/`H` split is the deferred Rule 19, which needs
git author signals. That is now an honest gap rather than a false claim.

### G2. Exchange files are entirely unlinted, and a skill says otherwise

`common.py` has no exchange-file iterator at all — no `iter_exchange_files`. Rule 2 walks kb
pages, spec files, and manifests; Rule 5 walks kb pages and spec files. Exchanges are in none of
them. Yet:

- `respond-exchange/SKILL.md:61` — "Run `python _framework/tools/lint.py`. Any `[[wikilinks]]`
  in your response **must resolve**." Lint does not check this.
- `exchange-protocol.md` requires briefs to carry a `## Context` section of `[[area:…]]`
  prefixed links — precisely the form Rule 2's area-prefix check exists for.

Same shape as the spec-file gap closed on 2026-08-30, and the fix is the same three lines:
an iterator plus two rule walks. Worth doing together with a decision about `exchanges/**`
frontmatter, which Rule 1 also never checks.

### G3. Nothing detects a role file that re-enumerates the skill baseline

`capabilities.md:30` — role files **reference** the baseline skill set, which is the "single
source of truth"; `capabilities.md:37` — "add it here and nowhere else"; `role-template.md:78` —
"don't re-enumerate them here, or the list drifts."

Nothing checks it. This exact drift is what caused the 2026-08-16 bug (a newly-shipped baseline
skill never reached existing roles because their `## Allowed skills` sections enumerated the old
list). It was fixed by migration, and the clause warning against a recurrence has no enforcer.

**Mechanizable:** a role file's `## Allowed skills` section, outside `# capability:` blocks,
should not list baseline skill names. Cheap grep-level check.

---

## Contradictions — normative docs that disagree with each other or with shipped behaviour

These are worse than gaps: `CLAUDE.md` tells agents the schema is normative and a conflicting
skill is a bug to be flagged. So an agent that reads these will act on the wrong one.

### C1. Commons is described as proposals-only; `/amend-commons` edits it directly

> The always-on protection: any change to `commons/` goes through `commons/_proposed/` first,
> with a human gate before promotion.
> — `promotion-protocol.md:3`, repeated verbatim at `spec.md:870`

`/amend-commons` shipped 2026-08-15 as a baseline skill and edits an existing commons page **in
place**, under a light gate (human confirmation in conversation + a `CHANGELOG.md` entry). Its
own SKILL.md:54 calls itself "the only sanctioned way to edit an existing commons page
directly."

Both statements can't hold. Under the schema-is-normative rule, an agent following
`promotion-protocol.md` should conclude `/amend-commons` is a bug and refuse it — the exact
failure mode that rule exists to prevent, inverted. The schema doc was never updated when the
skill landed.

**Fixed 2026-08-31.** Both sites now describe the human gate as taking one of two forms — new
content through `_proposed/` + `/promote`, corrections to an existing page through
`/amend-commons` under a lighter gate — and state that there is no third path. `CLAUDE.md:20,41`
gained the same routing.

### C2. `spec.md` describes telemetry instrumentation that doesn't exist

> The `pages_cited` list is populated by scanning agent outputs for `[[wikilink]]` references.
> The `bodies_loaded_beyond_preload` list comes from tracking file-read tool invocations during
> the session
> — `spec.md:934`

Neither is automated. `telemetry.py session-end` takes `--cited` and `--loaded` as
comma-separated arguments the agent supplies from memory, and `wrap-up/SKILL.md:82` is candid
about it: "Don't agonize over getting telemetry exactly right. Best-effort is fine."

The skill is right and the spec is wrong. This matters beyond tidiness: `/budget` and the
preload-prune analysis consume this data, and a reader of `spec.md` would take it for
instrumented measurement rather than agent self-report.

**Fixed 2026-08-31 by correcting the doc, not by building the automation.** The spec now says the
lists are agent-reported and best-effort, and should be read as a trend signal rather than an
exact count. Building it was considered and rejected for now: `session_state.py` already locates
and parses the session transcript, so scanning it for `Read` calls and wikilinks is feasible —
but the transcript is a Claude Code internal that the tools already treat as optional, and
telemetry is meant to work regardless of client. Documenting behaviour that silently doesn't
happen without a transcript would re-create this very class in a new form. Logged as an optional
enrichment, never as the documented mechanism.

### C3. The write-permission table still uses the dead `q-` exchange prefix

`spec.md:185` lists `exchanges/**/q-*.md` as an `A`-category path. Nothing `/exchange` writes has
ever been named `q-*` — ids are `ex-<date>-<slug>`. This is the same stale prefix that made
`kb_vitals`' exchange scan return zero for every project (fixed 2026-08-29); it survives here in
the normative spec. Harmless today because nothing reads the table, which is G1's point.

**Fixed 2026-08-31** — the row now reads `exchanges/**/ex-*.md`.

### C4. The exchange protocol teaches two unresolvable wikilink forms

Found while planning G2's fix. `link-conventions.md` says references to files outside `kb/` are
relative markdown links, and only kb pages are in the wikilink index. The exchange protocol
authors two references that violate this:

- `exchange-protocol.md:35` specifies the index line as `- [[<id>]] — <kind> from …` — a wikilink
  to another exchange file.
- `exchange-protocol.md:56`'s own example `## Context` contains
  `[[specs/2026-05-detector-thermal/brief]]` — a wikilink to a spec file.

Neither can ever resolve. The second is the worse one: it is the example an agent copies. Both
are blocking G2 (turning Rule 2 on for exchanges would flag every index line), and the options
are laid out in the future-work plan.

### C5. `exchanges/**/index.md` is categorised lint-maintained, and no lint maintains it

`spec.md:189` puts it in the `L` category — regenerated by lint, never hand-edited. Rule 15
regenerates `areas-index.md` and each `kb/index.md`, and nothing else. The `/exchange` skill
appends to the exchange index by hand, which is an `A`-category behaviour. Either Rule 15 should
own the file or the category is wrong; settling it also settles C4's index half, since a
generator can emit whichever link form is decided on.

---

## Advisory by design — correctly unenforceable

Recorded so a future pass doesn't re-open them. Each is a judgement a deterministic linter
cannot make, and none claims a checker exists.

| Clause | Where |
|---|---|
| "Never inherit context from a previous session — always reload from the role" | `CLAUDE.md:29` |
| "never propagate as fact until promoted to finding" | `CLAUDE.md:50` |
| "never silently supersede one with the other" (contradicting findings) | `CLAUDE.md:138` |
| "never silent truncation" of pulse content | `spec.md:714` — Rule 7's cap is the backstop |
| "`/ask` never writes to any file" | `ask/SKILL.md:42` |
| "You never write another area's pages" (reverse propagation) | `amend-commons/SKILL.md:55` |
| "commons pages are curated for a commons reader" | `promotion-protocol.md:69` — backfilled in Release 2026-08-31; see `maintaining.md` on un-lintable ≠ un-backfillable |
| single-line `question` event bodies | `CLAUDE.md:95` — the doc says the tool tolerates multi-line, and `_normalize_question` does |

---

## Enforced — the registry

Grouped by enforcer. Each row's clause text is verbatim enough to grep.

### Rule 1 — frontmatter validity
- "Write frontmatter at creation time with the required fields for the type" — `CLAUDE.md:58`
- "Knowledge pages in `kb/` come in four types" — `CLAUDE.md:17` (`VALID_TYPES`)
- manifests are "`type: source`, with an `s-` prefix" and "the same eight required fields" — `frontmatter.md:231`

### Rule 2 — forward-link integrity
- "Linking to a page with `status: superseded` is an error" (resolution half) — `CLAUDE.md:54`
- "Source pages: `provenance.raw_path` must resolve" — `lint-rules.md:27`
- "files outside `kb/` … use relative markdown links" — `link-conventions.md:24`
- "`[[data/manifests/…]]` can never resolve" — `frontmatter.md:256`
- `context_pages` are "wikilinks into `kb/`" — `lint-rules.md:49`

### Rule 5 — supersession integrity
- "A page with `status: superseded` must have `superseded_by` populated" — `link-conventions.md:56`
- "**Linking to a superseded page is an error**, not a warning" — `link-conventions.md:58`, `spec.md:772`

### Rule 6 — type-specific completeness
- "Required-at-creation fields (per type) are enforced by lint Rule 6" — `frontmatter.md:24`.
  *Imprecise but not a gap:* Rule 6 covers the type-specific fields; the eight all-type fields
  are Rule 1's. Worth a wording fix.
- "required if status is under_test or later" (`evidence`) — `frontmatter.md:139`

### Rule 7 — pulse size
- "pulse.md exceeding line cap is an error" — `spec.md:799`

### Rule 10 + `promote.py`
- "Two mechanisms surface a pending ack, so it can't be lost" — `promotion-protocol.md:80`.
  Both halves verified present (2026-08-17 and the Rule 10 module).

### Rule 15 — index maintenance (enforced by regeneration, not detection)
- "**Auto-generated by lint** (Rule 15); never hand-edited" — `index-format.md:7`
- "The linter regenerates the index on every run" — `index-format.md:113`

### Rule 17 — raw immutability
- "Existing files never modified" / "raw materials are immutable" — `CLAUDE.md:14,42`
- "Raw materials in `raw/` are immutable; agents read but never modify" — `spec.md:152,973`
- "Raw materials anywhere are read-only" — `role-template.md:68`

### Rule 3 + `.gitignore` (enforced by regeneration)
- "Authors never edit them" (backlink sidecars) — `link-conventions.md:44`, `spec.md:770`.
  Sidecars are regenerated every run and git-ignored (`.gitignore:30`).

### `framework.py`
- "`task_subagents` must be enabled" for `formal_review` — `capabilities.md:140`
  (`_DEPENDENCIES` at `framework.py:83`, checked before applying a plan)
- "Pruning never deletes the underlying kb pages" — `spec.md:291,421`
- "Prune respects capability blocks" — `framework/SKILL.md:88`

### `promote.py`
- "the proposal's `page.md` must carry a *source area* id, not a commons id" — `promotion-protocol.md:57`

### `framework_check.py`
- config `warnings_visible` == shipped warning rules — `lint-rules.md:167`
- "Always-visible rules always run … a disabled rule returns no findings" — `spec.md:789`
  (self-gating, verified per module)
