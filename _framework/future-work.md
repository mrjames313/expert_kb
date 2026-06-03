# Future work

A living log of design observations, bug-adjacent issues, and feature ideas that were surfaced during framework development and dogfooding but deliberately deferred. None of these are urgent; most need real usage evidence before deciding the right shape. This file exists so we don't relitigate every decision and so good ideas don't evaporate.

Format per item: what was observed, why it was deferred, what addressing it would look like, and any notes on triggering conditions ("revisit when...").

---

## Schema gaps

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

**Why all deferred:** None of these has caused observable pain yet in the dogfood project. Each requires picking a threshold that benefits from real usage data. The infrastructure to enable them is in place; the work is mostly writing the rule code + tests.

**Revisit when:** A specific pain point surfaces that one of these rules would address. Better to wait for the trigger than to ship pre-configured warnings that produce noise.

---

## Tooling

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
