# Future work

A living log of design observations, bug-adjacent issues, and feature ideas that were surfaced during framework development and dogfooding but deliberately deferred. None of these are urgent; most need real usage evidence before deciding the right shape. This file exists so we don't relitigate every decision and so good ideas don't evaporate.

Format per item: what was observed, why it was deferred, what addressing it would look like, and any notes on triggering conditions ("revisit when...").

---

## Schema gaps

### Promotion's "Awaiting your ack" INBOX entry is documented but unimplemented

**Observed during:** dogfooding `/promote` — `promotion-protocol.md` step 7 specifies that promotion files an INBOX entry under "Awaiting your ack" ("Promoted [[…]] — awaiting human review."). Neither `promote.py` (no INBOX reference at all) nor the `/promote` skill does it — the skill's step 7 is "Brief the user" and stops. Schema is normative, so the dogfooder filed the entry by hand and flagged the gap.

Same shape as the recurring series (the version stamp, `CONFIGURABLE_LINT_RULES`, the role skill baseline): **a documented behaviour with no implementation behind it.** It matters here because that ack entry is the *primary* "review this promotion" signal — without it a promoted page can sit at `human_reviewed: false` unnoticed, and the only backstop (Rule 10, promotion freshness) is itself unimplemented and time-delayed.

**What addressing it would look like** (small, clear — schema wins, so implement the schema): have `promote.py` append the "Awaiting your ack" entry to `INBOX.md` (it already knows the new commons id and page type), and update the `/promote` skill's step 7 to reflect that the tool does it. Mirror the wording promotion-protocol.md step 7 already specifies. Add a test asserting the INBOX line appears after promotion.

**Revisit when:** next touching `/promote`/`promote.py`, or sooner — it's a cheap fix and the missing signal is user-facing. (Candidate to just fix rather than defer.)

### Synthesis-finding provenance shape

**Observed during:** Review of `f-2026-05-26-private-placement-dd-best-practices`.

The current source/concept/finding/decision schema assumes findings have one of `kind: external | internal-experiment | internal-notes` provenance — implying the finding traces to a single source. Synthesis findings that aggregate evidence from many sources (the convergent-best-practices finding cited 12 sources) don't fit this shape cleanly. The author ended up pointing `ref` at one source and leaving `raw_path: ~`, which under-represents what the page actually is.

**Why deferred:** Only one synthesis finding has surfaced in the dogfood pass. Not enough evidence to know whether to add a new `kind: synthesis` value, relax the field to be optional for synthesis findings, or do something else.

**What addressing it would look like:**
- Add `kind: synthesis` (or similar) as a valid value. For synthesis findings, `provenance` carries just the kind + retrieved date; `evidence` list does the attribution work.
- Update `_framework/schema/frontmatter.md` documentation.
- No lint changes — the existing required-field check would still apply.

**Revisit when:** A second or third synthesis finding lands. The shape will be clearer with more examples.

### Source-page `interested_party` field

**Observed during:** Review of `f-2026-05-26-private-placement-dd-best-practices` and `c-2026-05-26-investor-side-dd-documentation-discipline`.

The convergence discipline (≥2 independent non-interested sources promotes a recommendation to finding) lives entirely in author prose. Subtleties like "Sidley + Bressler citing the same FINRA notice = one independent source" are hard to enforce mechanically because the framework has no idea which sources are interested parties.

**Why deferred:** Adding the field is easy; the harder question is whether to also add a lint rule that surfaces findings whose convergence depends on interested-party sources. The lint rule would require counting evidence and inferring convergence claims from prose — non-trivial.

**What addressing it would look like:**
- Add optional `interested_party: bool` to source frontmatter (default false).
- Document the field in `frontmatter.md` with guidance on when to set it true (vendor-published whitepapers; advocacy organizations on the topic they advocate; interpretations of a regulator's own rule by regulated parties).
- Optionally, a configurable warning lint rule that surfaces synthesis findings whose evidence list is majority-interested.

**Revisit when:** A second project surfaces similar convergence-counting subtleties.

### Decision-page `tests_concepts` field

**Observed during:** Review of `d-2026-05-27-dd-playbook-v1`.

The decision page implicitly tests `c-2026-05-26-investor-side-dd-documentation-discipline` (mentions it in the prologue, encodes its falsification condition inline). But there's no formal link in frontmatter that would let `/wrap-up` or a tool walk decisions and ask "what under_test concepts does this exercise?"

**Why deferred:** The feedback loop from decision-use back to concept-status would also need workflow support (see "Concept-lifecycle feedback loop" below). Adding just the field is easy but doesn't move the needle without the workflow piece.

**What addressing it would look like:**
- Add optional `tests_concepts: [list of [[wikilinks]]]` to decision frontmatter.
- Document in `frontmatter.md`.
- Update the decision-page body-structure guidance to mention: when a decision exercises an under_test concept, link it and articulate what the decision-use would reveal.
- Build the `/wrap-up` walk-and-ask piece simultaneously.

**Revisit when:** Adding the next under_test concept that a decision will operationalize. The pattern becomes clearer with more examples.

---

## Concept-lifecycle enforcement

### Configurable warning for stale `under_test` concepts

**Observed during:** Concept body-pattern work; both dogfood concepts (`c-2026-05-26-investor-side-dd-documentation-discipline` and `c-2026-05-26-three-stage-dd-process-structure`) are stuck at `under_test`/`developing` with no movement.

The framework now has body guidance for `under_test` concepts (in `frontmatter.md`) that asks for explicit promotion and falsification criteria. But without enforcement, concepts can still drift indefinitely. Especially in low-traffic projects, the agent has no reason to re-examine a concept's status unless explicitly prompted.

**Why deferred:** Without real usage data on how long concepts naturally sit at `under_test`, we'd have to guess at the staleness threshold. Setting it too tight produces noise; too loose and it never fires.

**What addressing it would look like:**
- New configurable warning lint rule (off by default): `concepts_at_under_test_for_N_active_days`.
- Threshold in `_framework/config.yml`: `concept_staleness_active_days: 60` (or similar).
- Rule surfaces concepts whose `updated` field is older than threshold and whose status is `under_test`.
- Suggested message: "concept X has been under_test for N days. Consider whether the promotion/falsification criteria are still right, whether new evidence has emerged, or whether to mark `dropped`."

**Revisit when:** A project's first concepts hit the 60-day mark and movement (or stagnation) becomes observable.

### Concept-lifecycle feedback loop via `/wrap-up`

**Observed during:** Decision-page review (the playbook tests a concept but has no closure mechanism); concept body-structure discussion.

When a decision exercises an under_test concept, real-world use of the decision should feed back to the concept's status. Currently this is implicit — the agent or human has to remember to revisit. Combined with the `tests_concepts` field above, `/wrap-up` could walk those concepts at session end and ask "what did this session's work reveal about each one?"

**Why deferred:** Requires the `tests_concepts` field first; also adds friction at wrap-up that may not be earned unless the concept is actually being exercised. Need real cases to test the right cadence.

**What addressing it would look like:**
- After `tests_concepts` exists, `/wrap-up` reads any decision pages whose work was touched this session and enumerates their `tests_concepts`.
- For each, prompt the user: "did this session's work bear on concept X? (promote / falsify / no change)"
- If promote or falsify, journal a concept-status-change event and update the concept page.

**Revisit when:** `tests_concepts` is added and at least one decision has it populated.

---

## Session lifecycle awareness

### Distributed lifecycle awareness across existing skills

**Observed during:** Dogfood-pass operational discussion about when to `/clear` and when to restart Claude Code.

The framework has clean session boundaries via `/start` (open) and `/wrap-up` (close), plus three Claude Code hooks (SessionStart, SessionEnd, PreCompact). But the *transitions* between sessions are unsupported. Specifically:

- **Role switches.** Going from role A to role B currently requires the user to remember three things in order: `/wrap-up` for A, then `/clear` (Claude Code primitive), then `/start B`. The middle step is on the user; forgetting it means B's session starts with A's context still loaded.
- **Resuming interrupted work.** If Claude Code exits without `/wrap-up`, the next session has no awareness of that fact — the user has to remember they were mid-flight in role X and explicitly `/start X` again. The pulse log being non-empty is a signal but no skill surfaces it.
- **Clean continuation within the same role for a new spec.** Less common, but the same friction — context from the previous spec lingers when it doesn't help the new one.

The friction isn't dramatic, but it's recurring and the cognitive load adds up over many sessions.

**Why deferred:** This needs more dogfood evidence on actual transition patterns — how often role switches happen, what fraction of sessions end without clean wrap-up, whether the friction is mostly role-switch or something else. Also touches multiple skills (cross-cutting concern), so the change is non-trivial.

**What addressing it would look like:**

A distributed approach where several existing skills become lifecycle-aware, sharing an on-disk session-state marker:

1. **Session-state marker on disk** — `_framework/telemetry/.session-state.json` recording current role, session-start timestamp, last wrap-up timestamp, whether the last exit was clean. Updated by `/start`, `/wrap-up`, and the session-end hook.

2. **`/start` detects state.** Before adopting the requested role, check the marker:
   - If a prior session is open and unwrapped: "Last session as role X didn't wrap up cleanly. Wrap-up first, or override and adopt Y now?" (Override is needed for cases where the prior session was abandoned and isn't recoverable.)
   - If `/start B` invoked while role A is active: detect role mismatch, recommend the wrap-up → `/clear` → `/start B` sequence explicitly with each step.

3. **`/wrap-up` asks about next action.** At the end of its flow: "Continuing this session, switching role, or done?" If continuing, suggest `/clear` for a clean frame. If switching, suggest `/clear` then `/start <new-role>`. If done, no action needed.

4. **Other skills detect mid-flight inconsistency.** `/plan`, `/implement`, `/ingest`, `/replan` could check the session-state marker on invocation. If invoked without a fresh `/start` after a `/clear` (i.e., the marker says role A was last wrapped up but no role is currently open), surface a brief reminder rather than silently proceeding.

5. **SessionStart hook surfaces last-session state.** Beyond the existing CLAUDE.md / areas-index / INBOX dump, also show: "Last session: role X, ended <cleanly | abruptly> on <date>. Run `/start X` to resume, or `/start <other>` to switch."

A new `/switch-role` skill *could* sit on top of this as a convenience wrapper for the common case, but it isn't required — the distributed awareness solves the core problem and `/switch-role` would just save one invocation.

**Revisit when:** v2 dogfood pass exercises multiple roles in the same project. Friction patterns will be clearer when there are 2-3 areas with separate roles being switched between in real work. Without that evidence, the design risks optimizing for cases that don't actually occur.

**Implementation order if this lands:** Session-state marker first (everything else depends on it). Then `/start` detection. Then `/wrap-up` end-prompt. Then SessionStart hook enrichment. Other skills' inconsistency detection last — likely overkill for v1 of this work; can wait for evidence it's needed.

---

## Commons growth control

### `commons_coverage` config parameter

**Observed during:** Commons-extension design discussion.

In a healthy project, commons-extension during the 2nd-area addition tends to surface the most candidates; subsequent additions should surface progressively fewer as commons stabilizes. If late additions are still surfacing many candidates, that's a signal — either the areas are genuinely disparate, or commons is being under-populated and is catching up.

The framework currently shows the user a context message during the review ("this is the project's Nth area; expect fewer candidates than the 2nd"). It doesn't enforce policy.

**Why deferred:** Adding policy without evidence of what the right thresholds look like would be guessing. The infrastructure to support a config parameter is in place; populating it is the part needing data.

**What addressing it would look like:**
- Add `commons_coverage:` section to `_framework/config.yml`:
  ```yaml
  commons_coverage:
    target_ratio: 0.3       # commons:area kb ratio considered "healthy"
    inflation_warning: 5    # warn if a single add-area surfaces >N candidates
  ```
- `commons_extension.py list` consults the config and adds warnings/biasing to the candidate ranking.
- The skill displays the warning when triggered.

**Revisit when:** A project has been through 3+ area additions and the typical candidate counts per addition become apparent.

---

## Configurable warning lint rules

A set of warning-tier lint rules with off-by-default infrastructure already in place (`_framework/config.yml`, `framework.py enable-lint`). Each just needs the actual rule code. Rules in roughly priority order of how often they'd matter:

### Rule 10 — Stale exchanges

Surface exchanges in `exchanges/<a>--<b>/` with `status: answered` for more than N active days without being closed. Counterpart to the open-question pulse work.

### Rule 14 — Stale promotions awaiting human review

Surface commons pages with `human_reviewed: false` aged past `promotion_freshness_active_days` (default 14, currently set in config). Referenced in `promotion-protocol.md` but the rule itself isn't yet implemented.

### Rule 9 — Preload staleness

Surface role-file preload entries whose target page hasn't been touched in N active days. Counterpart to `/framework prune`'s lifecycle-based pruning — adds an activity-based axis.

### Rule 16 — Cross-area heavy reads

Track how often each role reads into other areas' kb bodies (via telemetry). Surface roles whose cross-area body-read rate exceeds a threshold — they probably should be filing exchanges or using `/answer-from-kb` more.

### Rule 11 — Overlong specs

Surface spec directories whose `tasks.md` has more than N tasks, or whose total spec content exceeds a token threshold. Signal that the spec should probably be split.

### Rule 13 — POR staleness (when `por` is enabled)

Surface POR.md files that haven't been touched in N active days while the area has been actively producing work.

### Rule 8 — Slot lift candidates

Detect kb pages that appear in many roles' frontmatter-preload patterns and have been frequently body-loaded — candidates for promotion to full preload.

### Rule 4 — Cross-area finding citation patterns

Detect findings cited from multiple areas — candidates for `/propose-promotion`. Complements commons-extension by surfacing organic cross-area pressure outside of the area-addition moment.

### Rule 19 — Maintenance-category violations (previously slotted as Rule 18)

The originally-planned Rule 18 (now displaced by id uniqueness) — agent-vs-human write boundaries on maintenance pages. Needs distinguishing agent and human writes, which probably requires git author signals or a similar mechanism. Renumber to next free slot (Rule 19 or later).

**Why all deferred:** None of these has caused observable pain yet in the dogfood project. Each requires picking a threshold that benefits from real usage data. (Note: the shadow *infrastructure* is not actually in place — see below.)

**Revisit when:** A specific pain point surfaces that one of these rules would address. Better to wait for the trigger than to ship pre-configured warnings that produce noise.

### The shadow mechanism itself — reconsider or remove

The config and docs long described a "shadow" model: disabled warning rules still *run*, accumulate trigger counts, and surface a "consider enabling" suggestion past `shadow_suggest_threshold`. **It was never built** — the lint runner has no shadow logic and `shadow_suggest_threshold` is inert. The first implemented warning rules (20, 21, from the commons drift/link work) instead **self-gate** — they return nothing when disabled, which is simpler and quieter.

Open question: is shadow-with-suggestions worth building at all? It risks nagging users about rules they deliberately left off. Options: (a) drop it entirely and standardize on self-gating; (b) build it only if a real "you might want this rule on" need surfaces. **Leaning (a).** Until decided, keep new warning rules self-gating and treat `shadow_suggest_threshold` as vestigial.

---

## Tooling

### CI check: version stamp must move when framework machinery changes

**Observed during:** the missing-migration bug — commits landed after a version stamp without bumping it, so `/framework update` saw nothing new and skipped the migration. Commit 95a3fea fixed the root cause with *discipline* (bump `framework_version` + write an `UPGRADING.md` release entry; codified in `maintaining.md` → "Releasing a framework change"), but nothing *enforces* it. Machinery always arrives on pull; migrations only fire if the stamp moved. The same failure recurs the next time someone ships a fix without bumping.

This is now the standing backstop we said we'd add if the discipline slipped again (it's the fourth drift-of-a-hardcoded-fact issue in the series — see the enable-lint and role-baseline fixes).

**What addressing it would look like:** a CI check (or a pre-push hook, or a lint/`framework.py` self-check) roughly: "if any *pulled* path changed since the commit that last touched `framework_version` (`_framework/schema`, `_framework/tools`, `_framework/hooks`, `_framework/spec.md`, `_framework/adoption-guide.md`, `.claude/skills`, `CLAUDE.md`, `.claude/settings.json`), then `_framework/config.yml`'s `framework_version` must also have changed, and `UPGRADING.md` must contain a `**Release <that version>**` block." Fail the check otherwise. Git-history-based, runs in the framework repo only.

**Revisit when:** a release ships without a bump despite the discipline (then build it), or opportunistically if a CI pipeline is set up for the repo anyway.

### Real tokenizer for `token_estimate.py`

**Observed during:** Token-budget infrastructure work.

The current `token_estimate.py` uses chars/4 as a rough proxy. Real tokenizers (tiktoken or similar) would produce more accurate estimates for `/budget` and preload size calculations.

**Why deferred:** Chars/4 is reasonable for ordering preloads by relative size and surfacing the largest. Absolute accuracy doesn't matter for most uses. Adding a tokenizer adds a dependency.

**What addressing it would look like:**
- Add tiktoken (or anthropic's tokenizer if exposed) to `requirements.txt`.
- Replace the chars/4 estimate in `token_estimate.py`.
- Existing tests update to expect the new numbers.

**Revisit when:** `/budget` outputs are being used to make load-vs-not-load decisions where the chars/4 estimate is materially off (likely for code-heavy or non-English content).

### Telemetry tracking for `when_to_load` respect

**Observed during:** `when_to_load` field addition.

The skills now tell agents to consult `when_to_load` before opening a body. There's no telemetry that surfaces "the agent loaded this page even though its `when_to_load` suggested skipping for the task type." That'd be diagnostic data about whether the field is being respected.

**Why deferred:** Telemetry infrastructure is in place but enriching the load-event record with the `when_to_load` value plus a task-type tag is non-trivial. Also unclear whether the signal is actionable.

**What addressing it would look like:**
- Extend `telemetry.py session-end` to record loaded-pages along with their `when_to_load` text.
- Add a `/budget when_to_load-violations` reporter that surfaces pages loaded against their own guidance.
- Use the data to refine `when_to_load` text (or remove it if not useful).

**Revisit when:** A few projects have meaningful body-load telemetry and the `when_to_load` field is in wider use.

---

## Documentation

### Body-structure guidance for findings

**Observed during:** Convergent-best-practices finding review and concept-body work.

Concept bodies now have explicit pattern guidance in `frontmatter.md` (for `under_test` and later). Findings show emergent patterns too — at least synthesis findings tend toward phase-organized tables with inline convergence citations. Not codified.

**Why deferred:** Only one dense synthesis finding has been observed. The pattern might not generalize. Also, findings vary more by content type than concepts do — regulatory mechanics findings and synthesis findings look structurally different.

**What addressing it would look like:**
- Once 2-3 substantial findings exist in a project, look for patterns. If they cluster, add body-structure guidance for that cluster.
- Probably as a subsection in `frontmatter.md` under `### finding`, parallel to the concept body guidance.

**Revisit when:** Multiple substantial findings exist that can be compared.

### Body-structure guidance for decisions

**Observed during:** Decision-page (playbook) review.

Same as above for decisions. The playbook decision has a clear shape (procedural, branching, walk-away criteria), but a "should we switch X to Y" decision would look completely different. Hard to codify a single decision body pattern.

**Why deferred:** Decisions are the most structurally varied page type by their nature.

**What addressing it would look like:** Probably never as a single pattern. Could be a "decision types and their shapes" subsection if clusters emerge (procedural-artifact decisions, binary-choice decisions, etc.).

**Revisit when:** Multiple decisions of distinct shapes exist in a project. Might also just stay un-codified.

### Walk-away list single-source-of-truth pattern

**Observed during:** Decision-page review (the playbook had walk-away criteria duplicated in 3 places).

When content is repeated in 3+ places within a single page, the maintenance burden of keeping them consistent is real. A general pattern is: pick one canonical location, reference it from the others.

**Why deferred:** It's a style observation, not a framework feature.

**What addressing it would look like:** Could be a one-paragraph note in `frontmatter.md`'s body-structure guidance about avoiding triplication.

**Revisit when:** A second decision page exhibits the same triplication pattern, suggesting it's structural not stylistic.

---

## Operational

### Memory store audit pattern

**Observed during:** User noticed Claude Code writing to `~/.claude/projects/<hash>/` outside the framework.

The framework doesn't manage `~/.claude/projects/` — it's Claude Code's domain. But the existence of hidden memory cuts against the framework's "knowledge lives where you can see it" principle. Worth a documented audit habit.

**Why deferred:** This is operational advice, not a framework feature.

**What addressing it would look like:** A short note in `adoption-guide.md` recommending periodic audit of `~/.claude/projects/<project>/` to check that nothing project-specific is hiding there. Anything substantive that lands in memory should be in the kb.

**Revisit when:** Adoption guide gets a broader pass.

---

## Cross-area handoff is under-served

Two related gaps surfaced in the same dogfood pass: there is no way to *push* a targeted conclusion to another area, and the surface that actually controls what another area sees — role preload lists — has almost no tooling. They likely share a solution.

### A push/brief primitive (exchanges are pull-only)

**Observed during:** A promotion another area needed to know about, and a conclusion one area wanted to hand to another unprompted.

`/exchange` is pull-only — the asker requests information. There is no primitive for *pushing* a conclusion an area needs but wouldn't know to ask for. The only push channel is commons promotion, which is human-gated and project-wide — far too heavy for a targeted, one-time handoff. This gap also caused the `/propose-promotion` step-4 defect: with no push channel, the step reached for an illegal cross-area `_journal/pulse.log` write (fixed by routing through INBOX + `/exchange`, but that's a workaround, not the right primitive).

**Why deferred:** Needs a design decision on shape and on write boundaries — a push necessarily lands in another area's territory, which the ownership model forbids for direct writes.

**What addressing it would look like:**
- A `/brief` (or `/handoff`) skill that drops a note into a boundary-safe surface the target area owns and picks up — e.g. an area-scoped inbox, or an `exchanges/`-style record with `status: fyi` and no responder obligation.
- Whatever the shape, closing the loop with preload maintenance (below) is what makes the pushed content actually get loaded by the receiving role.

**Revisit when:** A second cross-area handoff need arises, or when tackling preload maintenance — they probably want a shared design.

**Status:** Implemented — see "Shipped: brief (proactive-A) mode for `/exchange`" below.

### Role preload lists are the real handoff surface and nothing maintains them

**Observed during:** An area transition where whether the receiving role would see the relevant pages depended entirely on a hand-edited preload list in `role.md`.

The preload list in each `role.md` decides what a role loads at session start — the highest-leverage file at an area transition — yet it is entirely hand-maintained. Additions surface only as INBOX suggestions needing human confirmation; pruning runs only through `/budget` and `/framework prune`. Nothing keeps a preload aligned with the knowledge actually accumulating, so a role can silently miss newly-relevant findings or decisions. The existing piecemeal ideas (Rule 8 slot-lift, Rule 9 preload-staleness above) each address one axis; what's missing is a cohesive, transition-timed proposal step.

**Why deferred:** The right degree of automation is unclear — too eager and it bloats preloads (the exact thing `/budget` fights); too passive and it's the status quo. Needs usage evidence on how preloads drift in practice.

**What addressing it would look like:**
- A skill (or `/wrap-up` / `/start` step) that, at an area transition, proposes a preload diff — pages whose `relevant_to`/citation patterns argue for inclusion in a given role, and stale entries to drop — consolidating Rule 8 and Rule 9's signals into one human-confirmed proposal.
- Human confirmation stays in the loop (preloads are `H`), but the *proposal* is generated rather than left to memory.

**Revisit when:** Preload drift causes a visible miss, or alongside the push/brief primitive above.

### `/add-role` skill with exchange onboarding

**Observed during:** Design of the brief (proactive-A) exchange mode. A brief's `open_for` set is frozen at file time, so a role created *after* a brief won't be obligated on it. That's the right call for the brief mechanism, but it leaves a new role blind to the area's accumulated cross-area knowledge.

There is also no tooled path today for adding a role to an *existing* area — roles are only created by `/add-area` (a new area, which has no exchange history) or at bootstrap. Hand-editing `role.md` is the current path.

**Why deferred:** Out of scope for the initial brief/exchange work; wanted to ship the exchange-specific parts first. The onboarding review only pays off once adding roles to populated areas is common.

**What addressing it would look like:**
- A `/add-role` skill for joining an existing area. Its distinguishing step: **review the area's exchange archive** — briefs directed to the area (`to_area`, including closed) and answered/closed queries in both directions (`from_area`/`to_area`) — filter by relevance to the new role's scope, and propose preload additions / kb citations (human-confirmed, since preloads are `H`). Voluntary incorporation only; the new role is never added to any frozen `open_for`.
- Converges with the preload-maintenance gap above: both are "generate a preload-diff proposal, human confirms."

**Revisit when:** Adding roles to populated areas becomes common, or right after the brief/exchange work lands.

---

## Commons twin edge: remaining gaps (post-5c/5d)

Surfaced by dogfooding the shipped twin-edge (below). These are the conspicuous holes given how much machinery the edge already has.

### Reverse-drift (commons → area) is enforced by nothing

**Observed during:** dogfooding `/amend-commons` — two twin heads-ups are sitting live in the project's INBOX for corrections that exist in commons but not in the research sources, and no rule will ever notice if they're ignored.

The twin edge is bidirectional in *markers* but not in *enforcement*. `aligned_on` lives only on the commons page, so Rule 20 catches one direction (source newer than commons). The reverse — a fix made in commons that the area source hasn't picked up — is "handled by" an `/amend-commons` INBOX heads-up, i.e. a note a human must read and act on. Nothing re-surfaces it if ignored. Given the investment in the edge, the missing half is conspicuous.

**What addressing it would look like** (needs a design decision — do not implement unilaterally):
- Option A: a second timestamp (e.g. `source_aligned_on` on the area page, or reuse `commons_twin` + a date) so a symmetric lint rule can catch commons→area lag. Cost: another field on the area page, more write-boundary surface.
- Option B: promote the heads-up from a one-time INBOX note to a standing lint finding (e.g. an open `question`/marker the area owner must close), so ignoring it stays visible.
- Option C: accept asymmetry by design and stop implying symmetry — make the docs say plainly that commons→area is a human-loop, not a detected one.

**Revisit when:** reverse-drift heads-ups start getting dropped (already happening in the dogfood project), or before promoting Rule 20 out of shadow for real use.

### `aligned_on` semantics are underspecified — and it drives a lint rule

**Observed during:** the same dogfood session — setting `aligned_on` for a *correction* (not a reconciliation) had no clear answer, and three sources point three ways:
- `/amend-commons` says set it only for drift reconciliation.
- The 2026-08-15 upgrade migration says set it to "today".
- The field's own comment says "last reconciled with the source."

For a correction, none of these answers it. The dogfooder set the **promotion date** (reasoning: that's when the two were genuinely last aligned; setting "today" would suppress exactly the drift signal Rule 20 was just enabled to show). Both "today" and "promotion date" are defensible from the docs — which means different projects populate it differently and **the rule's meaning isn't portable**. Note the migration's "today" is likely actively wrong for a *backfill* of an already-drifted page: it asserts alignment that may not hold and silences pre-existing drift.

**What addressing it would look like:** pick one definition — "the date the commons content was last known to match the source's content" is the strongest candidate (promotion date for an untouched page; the reconciliation date after `/amend-commons` reconciles; explicitly *not* "today" on a blind backfill). Then make all three sources say exactly that, and fix the migration guidance.

**Revisit when:** next touching `/amend-commons`, Rule 20, or the twin-edge docs — this is a cheap spec fix but changes populated data, so decide before more pages get an `aligned_on`.

### `human_reviewed` has no defined behavior for amendments

**Observed during:** dogfood `/amend-commons` — the dogfooder kept `human_reviewed: true` through an amendment, treating the light gate (human confirmation in conversation) as the ack. Defensible, but undefined: an amendment could equally be argued to reset it to `false` pending re-review. Undefined → non-portable, and Rule 10 (planned) keys on this field.

**What addressing it would look like:** state in `/amend-commons` + frontmatter.md whether an amendment preserves or resets `human_reviewed` (leaning: preserve — the light gate *is* the ack, matching the dogfood choice).

**Revisit when:** resolving the `aligned_on` semantics above (same doc-sweep), or when Rule 10 is implemented.

### Acknowledged, likely acceptable: Rule 20 is timestamp-based

Any source edit bumps `updated` and can fire Rule 20, including frontmatter-only edits that don't affect the commons copy. The docs already call this out as the price of a *warning* (not an error), and `set_source_twin` deliberately not bumping `updated` shows it was considered. Left here only so a future content-hash-based drift check has a home if the timestamp noise proves annoying.

## Shipped: commons drift & link management (5c/5d)

**Shipped across phases 1–5** (the commons-drift-mgmt work). Resolves report issues 5c (silent drift between an area page and its commons copy) and 5d (commons pages' links point back into areas). Design retained below for rationale.

**Architecture settled as COPY.** Dogfooding confirmed commons pages are full reference content (lookup tables, protocols, exact numbers) — *not* summaries — and that move/reference both break the load-bearing property that commons is self-contained and cheap to load (they force the cross-area read promotion exists to prevent). Distillation was rejected: it re-solves a cost problem `when_to_load` already handles, and routes readers into the very cross-area reads to avoid. So we keep the copy and *manage* the relationship.

**Model — copy full, then edit for a commons reader** (two operations, neither is summarization):
- **Strip resolved-deliberation cruft** — resolved-question sections, superseded sections, closed "left open" lists. This content actively misleads a cold reader. Skill guidance + agent judgment, not a hard rule.
- **Rewrite conceptual links to commons twins** (leave provenance links to area sources). Propose-for-review (not silent), bare `[[twin]]` form (commons→commons is same-area), alias-preserving, best-effort code-fence skip.

**Reads softened.** Occasional cross-area *reads* are acceptable; iterative needs use an exchange; *writes* into another area stay forbidden. This drops 5d to a **nudge**: a commons page citing an area page that has a twin should *prefer* the twin (self-containment, cheap loading, correct backlink attribution), but it isn't an error.

**Bidirectional twin edge, asymmetric markers.**
- Commons → area: `promoted_from_page` (list-capable, for future multi-source synthesis).
- Area → commons: `commons_twin` back-pointer. Writing this one field is a **narrow, framework-maintained exception** to write-boundaries — any role may set it during promotion/amend (metadata link, not content).
- `aligned_on` lives **only on the commons page**. Lint auto-detects the common direction (source `updated` > commons `aligned_on` → commons behind). The rare reverse (error fixed in commons) is handled by `/amend-commons` filing an **INBOX heads-up** to the area owner — no area-side timestamp.

**`/amend-commons` skill (keystone).** The sanctioned, general way to edit an *existing* commons page — corrections, link-rewrites, and drift reconciliation all flow through it. **Light gate**: direct edit + `CHANGELOG.md` entry + human confirmation in conversation. Any role may invoke.

**2A1 relaxation.** Promotion still does not supersede or move the source; it may now add the benign `commons_twin` back-pointer.

**Lint (two warning-tier rules, default shadowed):**
- *5c staleness* — commons page whose source's `updated` is newer than its `aligned_on`. Drift detection is **link-aware**: normalize area links through the twin map before comparing, since a twin's links differ from its source's by design.
- *5d twin-preference* — commons page citing an area page that has a commons twin → prefer the twin.

**Shared helpers.** A `commons_twin_map` + an alias/code-fence-aware `rewrite_links_to_twins`, used by `/promote`, `/amend-commons`, and the 5d lint (one implementation, three consumers).

**Work items (phased):**
1. **Record-keeping + helpers** — `commons_twin` (area), `aligned_on` (commons), list-capable `promoted_from_page`; the twin-map + link-rewrite helpers; sync frontmatter.md, promotion-protocol.md, spec, and CLAUDE.md (the back-pointer write exception + the softened reads stance).
2. **`/amend-commons`** — light gate, CHANGELOG entry, INBOX heads-up for reverse drift.
3. **Promotion process** — `/promote` + `/propose-promotion`: copy full, strip deliberation, rewrite links (propose-for-review), set twin fields.
4. **Lint** — the 5c staleness and 5d twin-preference rules (link-aware drift).
5. **Reads-softening docs** — multi_area "Cross-area reads" snippet, link-conventions, Rule 16 wording.

**Explicitly not pulled in:** promotion still doesn't pull a page's dependency graph along (not-yet-promoted deps stay area links until promoted, then the 5d nudge drives the retroactive rewrite); multi-source *synthesis* reconciliation is deferred (the list-capable field leaves room).

**Status:** Shipped (phases 1–5). Remaining follow-ups: decide the shadow-lint mechanism (above); if promotions get frequent, pull a page's dependency graph along on promotion; multi-source *synthesis* reconciliation (the field is already list-capable).

---

## Shipped: brief (proactive-A) mode for `/exchange`

**Shipped** in commits ~exchange-briefs 1–4; canonical behavior now lives in `exchange-protocol.md` and the exchange skills. Kept here for design rationale. Concretized the "push/brief primitive" note above. `/add-role` and the automated preload-diff engine are explicitly out of scope (deferred separately).

**Goal.** Extend `/exchange` from pull-only Q&A to also carry one-way *briefs* — an area hands a conclusion to specific role(s) in another area, with no responder obligation — reusing the exchange machinery, and fix the surfacing gap that makes any of it land.

**Locked decisions.** `kind: query | brief` (query default); one `/exchange` skill with a `--kind` arg (no separate `/brief` skill for now); neutral `from_area`/`from_role`/`to_area` fields (rename from asker/responder — template-only, no data migration); briefs add `to_roles` (snapshot at file time) + `open_for` (drained on disposition); per-role incremental disposition; `open_for` frozen (a new role catches up via the deferred `/add-role`, never auto-added); receiver disposes-and-closes (preload / file / cite / none); cross-area links use the `area:` prefix.

**Work items (all doc/skill edits — no Python):**

1. **Frontmatter schema** (`exchange-protocol.md`, spec §12, the `/exchange` template):
   - Rename `asker_area`/`asker_role`/`responder_area` → `from_area`/`from_role`/`to_area`.
   - Add `kind` (default `query`).
   - Brief-only: `to_roles: [...]`, `open_for: [...]`.
   - Kind-specific status: query `open → answered → [follow_up] → closed`; brief `open → closed` (closed ⇔ `open_for` empty).
   - Neutral, kind-aware index line (`<kind> from <from_role>@<from_area>`).

2. **`/exchange` skill** — add `--kind query|brief`; branch "When to use" (I-need-info vs they-need-info) and the written payload. A brief writes a statement + `to_roles`/`open_for` + a Context section using `[[area:…]]` prefixed links; no responder obligation.

3. **`/close-exchange` → generalized disposition** — the receiver's step. Query: the asker reviews the response, disposes (now including a preload option), closes. Brief: a targeted role disposes (preload *its own* `role.md` / file in its kb / cite / **none**), appends a `# Dispositions` entry, and drops itself from `open_for`; status flips to `closed` only when `open_for` is empty; declining is an explicit `none`. Decide whether to rename the skill for its dual use.

4. **`/respond-exchange`** — unchanged except the field rename; briefs never enter it.

5. **`/start` step 5** — add the exchange scan: for role R in area A, surface open queries `to_area==A` (respond), answered queries `from_area==A` (close), and briefs `to_area==A ∧ R∈open_for` (dispose). This also fixes the pre-existing query-surfacing gap — the respond/close skills already *assume* `/start` scans exchanges, but it currently doesn't.

6. **Docs sync** (per `maintaining.md`) — `exchange-protocol.md`, spec §12, CLAUDE.md "Cross-area reads."

**Out of scope (deferred):** `/add-role` + onboarding review, and the automated preload-diff engine — note the in-scope disposition still offers a *manual, human-confirmed* preload edit.

**Flags.** All `SKILL.md`/schema-doc edits — no code, so no automated tests; verify by reading + dogfood. Natural sequencing: schema → `/exchange` → generalized close → `/start` scan (3–4 commits).

**Remaining follow-ups:** `/add-role` + onboarding review (deferred, above); the automated preload-diff engine.

---

## Validated by dogfooding — preserve, don't regress

Not work items — design choices dogfooding confirmed are load-bearing. Recorded so a future "simplify the framework" pass doesn't quietly cut them.

- **"Schema is normative; skills are runbooks; when they disagree the schema wins — flag the skill as a bug."** This governance rule (in `CLAUDE.md` + `maintaining.md`) is what let a dogfood agent act *confidently* when `/promote` was wrong for its situation — instead of following the skill into a commons fork or stalling. Unusual and load-bearing; keep it explicit.
- **Preload token telemetry.** Surfacing "this role costs ~9,100 tokens/session, split full/frontmatter" is a concrete budget number most agent setups don't expose at all. Confirmed genuinely useful in practice — keep `/budget` and the per-role split.

## Done since this list started

For reference, items that started as "future work" and have since been completed (so they don't re-enter the backlog by mistake):

- `question-closed` event type and pulse_compact handling — done (commits ~pulse-fix).
- Duplicate-frontmatter detection in lint — done (commit ~brief-frontmatter-fix).
- Skill discovery (move from `_framework/skills/` to `.claude/skills/`) — done (commit 4-fix2).
- Hook schema correction in README + shipped `.claude/settings.json` — done (commit 4-fix).
- `when_to_load` field — done (commit ~when-to-load).
- Under_test concept body-pattern guidance — done (commit ~concept-body-guidance).
- Commons-extension during `/add-area` — done (commit ~commons-extension).
- `/promote` id-collision bug + Rule 18 (id uniqueness) — done (commit ~id-collision-fix).
- `new_commons_id` non-idempotence (silent `…-commons-commons-…` fork) + `/promote` rejects commons-id proposals — done (commit ~commons-id-idempotence).
- `→ to be filed:` path form ambiguity (spurious "not found on disk" warnings) — `pulse_compact.py` now tolerates the repo-root form; CLAUDE.md documents the field as kb-relative — done (commit ~filed-path-normalize).
- `enable-lint` rejected shipped warning rules 20/21 (hardcoded `CONFIGURABLE_LINT_RULES` drifted from the modules) — `framework.py` now derives the set from the shipped rule modules; template `config.yml` trimmed to shipped keys; lint-rules.md marks planned rules — done (commit ~enable-lint-derive). NB: the 8 planned configurable rules (4/8/9/10/11/13/14/16) in the section above remain unimplemented.
- Rule 20 silently skipped commons pages missing `aligned_on`/`promoted_from_page` (false negative — enabled rule reported `lint: clean` while checking nothing) — it now surfaces each un-checkable page by name, doubling as the twin-edge backfill worklist; 2026-08-15 migration reworded accordingly — done (commit ~rule20-loud-skip).
- No capability re-splice on upgrade (stale CLAUDE.md capability sections + role `# capability:` blocks survived upgrades silently; Step 4 said "leave intact") — added `/framework resync` which re-splices enabled capabilities' marker-delimited content from current snippets (content-only, non-destructive); upgrade Step 4 now runs it — done (commit ~framework-resync).
- Role files enumerated the always-available skill baseline, so new baseline skills (`amend-commons`) never reached existing roles — moved the baseline to `capabilities.md` → "Always-available skills" (single source of truth); implementer role-template now references it; also fixed the drift-prone "sixteen skills" count. Coordinator/reviewer keep deliberate restricted lists. Migration in Release 2026-08-16 — done (commit ~role-skills-baseline).
