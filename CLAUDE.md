# Project operating manual

This is the schema document for agents working in this project. It contains operating principles, not domain knowledge. Read it end-to-end before doing any work; refer back when uncertain.

The file is reshaped by the `/framework` skill when capabilities are enabled or disabled. Do not edit by hand.

## What this project is

See `commons/brief.md` for the project's mission and objectives.

## How knowledge is organized

Two layers:
- `raw/` — immutable source materials (PDFs, transcripts, web clips). Existing files never modified. New materials are added through `/ingest`, which also creates the corresponding source-summary page.
- `kb/` — the wiki, agent-maintained. The structured artifact that compounds.

Knowledge pages in `kb/` come in four types: `source`, `concept`, `finding`, `decision`. See `_framework/schema/frontmatter.md` for type details, status lifecycles, and required fields.

**Path-based ownership.** Every file's location says who owns it:
- `commons/` is jointly stewarded; direct writes are forbidden; use `/propose-promotion`.
- `areas/<area>/` is owned by that area's roles.
- `areas/<a>/<sub>/` is owned by the sub-area; sub-areas explicitly inherit parent context via role preload lists (no implicit inheritance).

## How to start a session

1. Read `INBOX.md` and `areas-index.md` (loaded automatically by the SessionStart hook).
2. Identify the area and role most relevant to the user's request.
3. Adopt a role by loading its preload list — both tiers (see "Loading context" below). The role file is the contract.
4. Never inherit context from a previous session — always reload from the role.

## Communicating with the human

**Conversation is the dominant mode of interaction.** Ask questions, surface uncertainties, request approvals, and discuss findings in conversation.

INBOX.md is supplementary — items that arose outside a conversation, items the human will see later, async attention. When the human is in session, default to conversation. Don't file an INBOX item for something you can ask directly.

## When to write where

- Findings, decisions, concepts within your area: write directly to area `kb/`.
- Same content that's project-wide: write to your area's `kb/`, then `/propose-promotion`.
- Never write directly to `commons/` — proposals only.
- Never modify files in any `raw/` directory — raw materials are immutable. New raw materials are added through `/ingest`.
- **One sanctioned cross-area write:** any role may set or update the `commons_twin` back-pointer field on an area page as part of promotion — it's a framework-maintained metadata link between a page and its commons twin, not content.

## How to interpret types

Quick reference; full details in `_framework/schema/frontmatter.md`.

- **source**: external; cite when used; preserve provenance.
- **concept**: hypothesis or claim with a status stage; never propagate as fact until promoted to finding. Surface a concept's status when citing ("we're testing whether...", "we have evidence that...", "we have falsified...").
- **finding**: established understanding; treat as given background.
- **decision**: prescriptive choice; alternatives noted; check supersession.

Linking to a page with `status: superseded` is an error — follow `superseded_by`.

## Frontmatter discipline

Write frontmatter at creation time with the required fields for the type. Update `updated` and any type-specific fields whose meaning changed when the body changes substantively. Type transitions (e.g., concept → finding) happen through `/promote`, never by hand-editing.

Pages are created through several paths: `/ingest` produces source pages; `/ask` synthesis may produce findings or concepts; in-conversation work surfaces concepts (often at `seed` or `developing`); `/wrap-up` materializes pulse-log entries into pages. See `_framework/schema/frontmatter.md` for the full discipline.

When you create or substantively update a notable page (high-confidence finding, decision, frequently-cited concept), evaluate whether it should be in some role's preload list — see "Suggesting preload updates" below.

## Loading context

A role's preload list has two tiers:

- **Full preload** — small, curated; bodies loaded.
- **Frontmatter preload** — broad; only frontmatter blocks loaded (directory patterns).

The `start` skill loads both at session start. During work, when evaluating whether to load additional pages: read frontmatter first (`summary`, `type`, `status`, `relevant_to`, and `when_to_load` if present — visible in the frontmatter preload or in `kb/index.md`). Load the full body only when the page is materially relevant to the task, when you intend to cite or build on its content, or when frontmatter indicates ambiguity worth resolving.

`when_to_load` is a page-authored hint about task fit — where `summary` describes what the page contains, `when_to_load` describes when a given task makes the body worth opening (and often when to skip it for a cheaper alternative). Respect it when present; treat its absence as "fall back to summary + relevant_to."

**Be intentional about what you load.** Many bodies is rarely justified; many frontmatter blocks usually is. See `_framework/schema/index-format.md` for `kb/index.md`, which agents reach for to discover pages outside their preload.

## Links and provenance

Use `[[wikilinks]]` for kb cross-references. Forward links are written by agents; the linter maintains backlinks via `.links.json` sidecars. When a wikilink points into another area or commons, prefix the target with its area for readability — `[[engineering:findings/f-...]]`, `[[commons:...]]`, nested `[[research/optics:...]]`; lint errors if the prefix names the wrong area. See `_framework/schema/link-conventions.md` for details, including the convention for content-consistency checks when updating pages with backlinkers.

## Pulse discipline

Append events to `_journal/pulse.log` during the session. Substantive decisions, surfaced findings, focus shifts, and resolved open questions all get logged. The format is:

```
## [YYYY-MM-DD HH:MM] <event-type> <role>
<1–3 lines describing the event>
→ to be filed: <kb-path> (when the event will become a kb page)
```

Event types: `decision`, `finding`, `concept`, `focus-shift`, `question`, `question-closed`.

Keep a `question` event's body to a **single line**. When it's materialized into `pulse.md`'s Open questions, the text is collapsed to one line (whitespace normalized); a multi-line body would still round-trip correctly, but writing one line keeps what you log identical to what a later `→ closes:` must match.

`question-closed` events use a slightly different directive — they retire an open question. Format:

```
## [YYYY-MM-DD HH:MM] question-closed <role>
<1–2 lines on the resolution>
→ closes: <verbatim text of the question being closed>
```

One entry can include multiple `→ closes:` directives if a single decision resolved several questions. The closure text should match the original question's text (matching is case-insensitive and tolerant of trailing punctuation). When `/wrap-up` compacts, retired questions are removed from `pulse.md`'s Open questions section.

Before `/clear` or end of session: invoke `/wrap-up`. The skill compacts the pulse log into `pulse.md`, files pending pages, prompts POR updates if `por` is enabled, and runs lint. `pulse.md` is bounded; lint enforces the line cap.

## Suggesting preload updates

When you create or substantively update a notable page, file an INBOX entry under "Heads up" if you believe the page should be in some role's preload list. Format:

> **Preload suggestion**: Consider adding [[<page>]] to `<role-file-path>` (full | frontmatter tier). Reason: <one-line rationale>.

The human reviews and either accepts (you edit the role file with explicit human confirmation) or declines. Don't repeat declined suggestions.

The complementary mechanism — identifying pages that should be **removed** from preloads — runs as cross-session analysis through `/budget` and `/framework prune`. You don't surface prune candidates per-page during work; the analyzer handles that. When you transition a page's status to `superseded`, `dropped`, or `falsified`, the framework files an INBOX heads-up pointing to any role files that reference the page.

## Spec lifecycle

brief → plan → tasks → execution → outcome. Each transition is a human gate, decided in conversation. `/replan` can fire from any point; appends to `revisions.md`; updates plan and/or tasks.

**When to replan**: when a task's outcome invalidates a downstream assumption in plan.md, when reviewer feedback identifies a structural issue, or when the work has materially diverged from the approved plan. Don't replan for minor scope tweaks within a task — those go in the task's Implementation Notes.

## Skills

Skills may be invoked explicitly by slash command (`/ingest`, `/plan`, etc.) or autonomously when the request matches the skill's trigger conditions.

The set of available skills depends on which capabilities are enabled. The `start` skill surfaces the active skill set at session start; the `/framework` skill manages capability state.

**Schema is normative.** A skill (`.claude/skills/<name>/SKILL.md`) is a runbook; the schema document it implements (`_framework/schema/*.md`, plus this file and the templates under `_framework/schema/spec-template/`) is the specification. When a skill and its schema disagree, **the schema wins** — follow the schema, don't take the skill's contradicting step, and flag the skill as a bug (INBOX "Heads up") so it gets reconciled. Watch especially for a skill that tells you to write outside your area, mark a still-cited page `superseded`, or skip a human phase gate.

## Escalation triggers

When to stop and ask the human in conversation:

- A change touches `commons/` — invoke `/propose-promotion`, do not write directly.
- Two findings contradict — never silently supersede one with the other. File a concept that surfaces the conflict (`status: under_test`) and ask the human in conversation.
- A spec's outcome diverges materially from the plan — `/replan`, do not improvise.
- An area boundary needs to change — do not move files unilaterally.
- A request spans multiple areas with no obvious lead — do not pick an area unilaterally.
