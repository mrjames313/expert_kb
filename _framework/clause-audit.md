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
same day. G2 — with C4 and C5, which were found while planning it — shipped 2026-08-31; a fourth
issue found the same way (C6, sub-area exchange directories) shipped with them. G3 remains
planned in the framework repo's backlog.

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

### G1b. `/start <role>` skipped orientation entirely — fixed 2026-08-31

Found while acting on the hooks report. `/start`'s reads of `areas-index.md` and `INBOX.md` sat
inside the *no-role* branch, so naming your role — the common case — skipped them. A user who ran
`/start researcher` never saw "Needs decision" items meant to block work. Independent of hooks,
and the real defect behind a report that blamed them. `/start` now runs
`session-start.sh --orient-only` as step 1, unconditionally.

### G2. Exchange files are entirely unlinted, and a skill says otherwise — fixed 2026-08-31

`common.py` had no exchange-file iterator at all. Rule 2 walked kb pages, spec files and
manifests; Rule 5 walked kb pages and spec files. Exchanges were in none of them — while
`respond-exchange/SKILL.md` told the responder to run lint *because* "any `[[wikilinks]]` in your
response **must resolve**", and `exchange-protocol.md` requires a `## Context` section of
`[[area:…]]` prefixed links, precisely the form Rule 2's area-prefix check exists for.

**Fixed** with `common.iter_exchange_files` (`exchanges/*/ex-*.md`; the `ex-` prefix pinned by
test, since that naming contract has already broken once), walked by Rules 2 and 5. Exchange
frontmatter is a different schema — only three of Rule 1's eight required fields exist on an
exchange — so it became **Rule 22** rather than an extension of Rule 1. C4 and C5 below were
prerequisites and shipped in the same change.

### G3. Nothing detects a role file that re-enumerates the skill baseline

`capabilities.md:30` — role files **reference** the baseline skill set, which is the "single
source of truth"; `capabilities.md:37` — "add it here and nowhere else"; `role-template.md:78` —
"don't re-enumerate them here, or the list drifts."

Nothing checks it. This exact drift is what caused the 2026-08-16 bug (a newly-shipped baseline
skill never reached existing roles because their `## Allowed skills` sections enumerated the old
list). It was fixed by migration, and the clause warning against a recurrence has no enforcer.

**Mechanizable:** a role file's `## Allowed skills` section, outside `# capability:` blocks,
should not list baseline skill names. Cheap grep-level check.

### G4. A query in `follow_up` is stranded — no consumer surfaces it

Found 2026-08-31 while reconciling `/close-exchange` against the protocol. `exchange-protocol.md`
defines the query cycle as "the asker fills the Follow-up section, sets status `follow_up`, and
the responder cycle repeats", and `spec.md` lists `follow_up` in the query status vocabulary.
Nothing routes it:

- `kb_vitals.exchange_counts` counts `open` → `/respond-exchange` and `answered` →
  `/close-exchange`. `follow_up` falls through both branches.
- `respond-exchange/SKILL.md` scans for `kind: query`, `status: open`.
- `/start`'s scan surfaces "open queries with `to_area` == this area".
- Rule 14 (exchange staleness, still unimplemented) is specified as `status: open` past the
  threshold, so a stranded follow-up would not age into a warning either.

Same shape as C6: not an error anywhere, the exchange is simply never handed to the role that
owes the next answer. `/close-exchange` step 3 said `status: open` — contradicting the protocol,
but accidentally keeping the routing alive. Corrected to `follow_up` under schema-wins, which
makes the gap reachable rather than masked.

**Fix (not yet made):** treat `follow_up` as responder-actionable wherever `open` is — the
`to_answer` branch of `exchange_counts`, `/respond-exchange`'s scan, `/start`'s surfacing, and
Rule 14's threshold when it lands. Rule 22 already accepts the status, so no lint change. Worth
doing with Rule 14, which needs the same predicate.

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

### C4. The exchange protocol teaches two unresolvable wikilink forms — fixed 2026-08-31

Found while planning G2's fix. `link-conventions.md` says references to files outside `kb/` are
relative markdown links, and only kb pages are in the wikilink index. The exchange protocol
authored two references that violated this — the index line (`- [[<id>]] — <kind> from …`, a
wikilink to another exchange) and its own example `## Context`
(`[[specs/2026-05-detector-thermal/brief]]`, a wikilink to a spec file). Neither could ever
resolve, and the second was the worse one: it was the example an agent copies.

**Fixed.** Both are now relative markdown links. The index half fell out of C5's resolution — a
generator emits whichever form is decided on — and the example is now a real relative path, which
Rule 2 resolves like any other. The protocol gained a "Linking from an exchange" section stating
the split, and both `/exchange` templates say it inline.

### C5. `exchanges/**/index.md` is categorised lint-maintained, and no lint maintains it — fixed 2026-08-31

`spec.md` put it in the `L` category — regenerated by lint, never hand-edited — while Rule 15
regenerated `areas-index.md` and each `kb/index.md` and nothing else. Three skills appended to or
rewrote the exchange index by hand, which is `A`-category behaviour, and each was copying a
`status` the exchange file's own frontmatter already carried.

**Fixed by making the category true:** Rule 15 now generates each `exchanges/<a>--<b>/index.md`
from the pair's exchange frontmatter, and the hand-edit step is gone from `/exchange`,
`/respond-exchange` and `/close-exchange`. Deliberately not gated on `multi_area` — exchange
directories survive disabling the capability, and an index that silently stopped tracking the
files beside it is worse than one kept honest. Downstream projects with hand-annotated indexes
are warned in the Release 2026-08-31 migration; `README.md` is where such notes belong.

### C6. Sub-area exchanges file into a directory nothing can see — fixed 2026-08-31

Found while writing G2's iterator. Exchange directories are `<a>--<b>` with the areas sorted, and
every consumer globs exactly one level: `kb_vitals.exchange_counts`, `/start`,
`/respond-exchange` and `/close-exchange` all scan `exchanges/*/`. A sub-area id carries a slash,
so `to_area: research/optics` produced `exchanges/engineering--research/optics/` — nested, and
invisible to all four. Sub-areas are plainly contemplated elsewhere (`kb_vitals._bare_area`
exists to normalise `areas/research/optics`); the directory scheme simply had no form for them.

Worse than an error, because it isn't one: the exchange is filed, lint passes, and it never
reaches the role that owes it a response.

**Fixed** by flattening a slash to `-` (`exchanges/engineering--research-optics/`), which leaves
every existing one-level glob working, and by having Rule 22 check that a file sits in the
canonical directory for its pair. No migration — the shape was unreachable in practice, since
no project had filed a sub-area exchange.

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
- "Any `[[wikilinks]]` in your response **must resolve**" — `respond-exchange/SKILL.md`.
  *The clause that named this rule before the rule could see the file* (G2).

### Rule 5 — supersession integrity
- "A page with `status: superseded` must have `superseded_by` populated" — `link-conventions.md:56`
- "**Linking to a superseded page is an error**, not a warning" — `link-conventions.md:58`, `spec.md:772`.
  Scope now includes exchange files, where the receiving area may preload what an answer cites.

### Rule 22 — exchange frontmatter validity
- "`status: open | answered | follow_up | closed`" (query) and "`open | closed` (closed when
  `open_for` is empty)" (brief) — `exchange-protocol.md`, both example blocks
- "`open_for` is **frozen**" and is drained from the `to_roles` snapshot — `exchange-protocol.md`
- "the id is `ex-YYYY-MM-DD-<slug>`" — `exchange/SKILL.md` step 4
- "One canonical directory per pair regardless of direction" — `exchange-protocol.md`

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
- `exchanges/**/index.md` as an `L`-category path — `spec.md`. *Was the category without the
  machinery* (C5); Rule 15 now generates it.

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
