# Adoption Guide

This guide takes you from zero to working.

1. **Minimal kickoff** — what you need to start.
2. **A day in the life** — how to interact with the framework once it's set up.
3. **Extending** — capabilities to turn on as your project grows.
4. **The rest** — pointer to the full spec.

---

## Minimal kickoff

### Two principles to start with

**Areas are workspaces; commons holds shared knowledge.** A project has one or more areas — research, engineering, product, business model, or whatever your project is composed of. Each area is a folder with its own knowledge base (`kb/`), raw materials (`raw/`), code, and data. You work in one area at a time. Everything project-wide — the mission, distilled findings, key decisions — lives in `commons/`. You don't write to commons directly; findings get promoted from areas through a small protocol.

**Roles guide context loading.** Each area defines agent roles (e.g., `researcher`, `engineer`) with an explicit preload list — the files agents load when working in that role. As you write knowledge pages, their frontmatter (summary, type, `relevant_to`) helps agents decide what else to bring into context. You don't tell agents what to load on the fly; your role files and frontmatter say it for you.

That's enough conceptual ground to start.

### Setup

Launch Claude Code in a fresh directory, then ask it to follow the setup guide:

> Follow the setup instructions at https://github.com/mrjames313/expert_kb/blob/main/SETUP.md

Claude will read the guide, ask you a handful of questions (project name, what it's about, your first area, your first role), and bootstrap the project for you. The whole thing takes a few minutes.

The setup creates one area and one role to start. You can add more areas and capabilities later through the `/framework` skill (covered below).

### Skills

Plain-language conversation is the primary way to interact with the framework. The agent picks the right skill based on what you're asking. Some of the skills you'll see invoked early on:

- `ingest` — file an external paper, transcript, or web clip; produces a structured source page with provenance.
- `ask` — query the wiki, synthesize an answer from existing pages.
- `plan` — start a spec (brief → plan → tasks) for a piece of work too big for one session.
- `wrap-up` — compact the working log into the pulse file and run lint at end of session.
- `check` — run the linter on demand; surfaces broken links, missing fields, stale items.

If you want to invoke a skill explicitly, use the slash command form (`/ingest`, `/plan`, `/check`, etc.).

---

## A day in the life

Once setup is done, working in the framework feels like a normal Claude Code conversation with a few helpful habits.

**Starting a session.** Open Claude Code in your project directory. The SessionStart hook loads `CLAUDE.md`, `areas-index.md`, and `INBOX.md` automatically — the agent now knows the project shape and what's waiting for you. Before diving in, glance at INBOX: anything in "Needs decision" blocks work; anything in "Awaiting your ack" is a recent promotion to commons for you to confirm; "Heads up" items are FYI.

If you're not sure where you left off, ask: "What's the current state of [area]?" The agent will load pulse and any open exchanges or in-flight specs and summarize.

**Asking and acting.** Talk to the agent in plain language. Some examples:

- "Look into [topic]" / "What do we know about [X]?" — research or synthesis from existing pages.
- "Ingest this paper / transcript / web page" — files an external source with provenance.
- "What are some approaches to [problem]?" — ideation; new concepts file as seed or developing.
- "Plan a study to test [hypothesis]" — starts a spec (brief → plan → tasks).
- "Implement task T3 of the [name] spec" — does that piece of work.
- "Reconsider our finding about [X] given this new source" — revision; the agent updates pages and flags affected backlinks.

The agent picks the right skill based on the request.

**Choosing area and role.** Most of the time you don't need to say which area or role — the agent figures it out from what you're asking. There are three ways to be explicit when you want to:

- **Inline hint in the request.** "Look at thermal management in engineering" or "as a researcher, what do we know about X?" — the agent uses the hint and routes directly.
- **`/start <role> <request>`** — slash command form skips inference entirely and adopts the named role.
- **Plain-language switch mid-session.** "Switch to engineering" or "I want to work as product-manager now" — the agent loads the new role's preload list.

You'll typically need to specify in three situations: the request is ambiguous between areas and the agent would otherwise have to ask; you're switching mid-session from a different role; or you want a specific role from the start (often the coordinator role, when enabled).

Read-only questions about another area don't trigger a role switch. If you're loaded as `optics-researcher` and ask "what's in engineering's pulse?", the agent stays in role and reads engineering's pulse to answer — switches only happen when work would require writes outside the current role's boundaries.

For requests that genuinely span multiple areas (e.g., "coordinate the handoff between research and engineering"), the coordinator role handles it when `por` is enabled; without `por`, the agent will ask you to break the work into per-area pieces.

**Checking on things.** Three places to look:

- **INBOX** — items needing your input or attention.
- **Pulse** in any area — current state (focus, open questions, recent decisions and findings, active concepts).
- **`/check`** — runs the linter on demand; shows broken links, missing fields, stale items, and shadow-rule suggestions.

**Wrapping up.** Before closing a session or running `/clear`, invoke `/wrap-up`. It compacts the working log (`_journal/pulse.log`) into the area's `pulse.md`, files any pending findings or decisions as kb pages, prompts you to update POR if relevant changes happened (when POR is enabled), and runs lint. The PreCompact and SessionEnd hooks run wrap-up as a safety net, but invoking it manually lets you review what gets filed.

If you forget to wrap up, no work is lost — the log persists. The next session's first read will detect the unflushed log and offer to compact it.

---

## Extending

Four togglable capabilities add machinery when their functionality becomes useful. Toggle them through the `/framework` skill — never by editing config or files directly. The skill handles CLAUDE.md edits, role file updates, file creation, and skill registration in one atomic operation.

### `multi_area` — off by default

**When to use**: a second area has shown up, and you want agents in area A to get authoritative answers from area B without reading through all of B's pages. Often the answer already exists; the exchange is just the path to surface it.

**What it adds**: pairwise Q&A directories between areas (`exchanges/<a>--<b>/`) and the skills `/exchange`, `/respond-exchange`, `/close-exchange`, `/answer-from-kb`.

**To enable**: `/framework enable multi_area`

### `por` — off by default

**When to use**: you have multiple workstreams in flight within an area and you can't quickly tell where you are in any of them. The brief tells you what the area does; pulse tells you what's hot this week; the middle layer ("we're in phase 2 of 4 on workstream X, blocked on Y") is missing. POR also includes generating and following written, structured plans — useful after initial exploration is done and the shape of the project (commons and areas) can be formed.

**What it adds**: a `POR.md` file in commons and in each area, loaded into every role's preload list. A `coordinator` role appears in `commons/` for cross-area planning. The `wrap-up` skill prompts you to update POR when relevant events happen during a session.

**To enable**: `/framework enable por`

### `task_subagents` — off by default

**When to use**: tasks within a spec are big enough that running them in your main session risks context exhaustion. Or you find yourself wanting cleaner separation between planning and doing — the same agent juggling both blurs the line.

**What it adds**: when `/implement <task>` runs, it spawns a fresh subagent that loads context from the role's preload list (not from the parent's working context). The subagent executes one task in a clean slate.

**To enable**: `/framework enable task_subagents`

### `formal_review` — off by default, requires `task_subagents`

**When to use**: you want rigor on the gates. Implementer agents should be reviewed by an independent agent before closing a task. Promotions to commons should get verdicts from each other area, not just your single sign-off. Repeated failures should trigger root-cause investigation rather than another retry.

**What it adds**: after each task, a reviewer subagent reads the output against the spec and writes a verdict. Two rejections trigger an auto-debug subagent that investigates in clean context. Promotions to commons spawn verdict subagents in each other area's reviewer role; consensus rules apply (all-approve auto-promotes; any objection escalates to you; all-abstain you decide).

**To enable**: `/framework enable formal_review` (will offer to enable `task_subagents` if not already on)

### Lint warnings — adaptive

All linter rules always run. By default the **error rules** are visible (frontmatter validity, broken links, supersession integrity, raw immutability — the correctness checks). The **warning rules** run in shadow mode — they evaluate but don't display. Instead, when a shadowed rule accumulates enough findings to suggest it's worth seeing, the linter adds a suggestion at the bottom of your next `/check` output:

```
Disabled lint rules with significant findings:
  Rule 4 (orphans) — 12 findings
  Rule 11 (spec abandonment) — 3 findings

Consider enabling: /framework enable-lint rule_4
```

You won't see noise from day one. You'll find out when a rule starts mattering for your project.

- `/framework enable-lint <rule>` makes a warning visible.
- `/framework disable-lint <rule>` returns it to shadow mode.
- `/framework lint-status` shows what's visible vs shadowed and recent trigger counts.

### Disabling

`/framework disable <capability>` undoes a capability. Files the capability created (POR files, exchange directories) stay on disk; they just stop being referenced. Re-enabling later picks them up where they were. You don't lose work by toggling.

---

## The rest

Once you've worked through a real piece of project and have a feel for what functionality is useful for you, the full framework specification lives at `_framework/spec.md`. It covers:

- **Directory layout** — every folder, what's framework infrastructure (`_framework/`), what's content, what's lint-generated.
- **File maintenance categories** — which files humans edit, which agents maintain, which the linter regenerates.
- **Frontmatter spec** — the four types (source, concept, finding, decision), their lifecycles, and field requirements.
- **CLAUDE.md** — the schema document; what it always contains and what capability-gated sections add.
- **Role files** — full shape, the explicit-inheritance rule for sub-areas, reviewer and coordinator variants.
- **Pulse mechanics** — the `pulse.md` + `_journal/pulse.log` pair, compaction rules, hook integration.
- **Specs** — the full template (brief → plan → tasks → revisions → outcome), phase gates, and the `/replan` flow.
- **POR** (when `por` is on) — file shape and update discipline.
- **Exchange protocol** (when `exchanges` is on) — filing, responding, follow-up, closing.
- **Promotion-review protocol** — proposed → reviewed → promoted, with single-gate and formal-review variants.
- **Subagent pattern** (when `task_subagents` is on) — invocation, context loading, retry and auto-debug.
- **Lint rules** — all 18, with thresholds, shadow behavior, and the configuration file.
- **Skills** — the always-available set plus the capability-gated ones.
- **Raw materials and data manifests** — the raw/wiki two-layer split, manifest fields, lineage tracking.
- **Link conventions** — wikilinks, backlink sidecars, content-consistency convention.

Read it once you've felt your way through a project's worth of minimal-mode work. The parts that matter will jump out; the rest can wait until they earn their place.
