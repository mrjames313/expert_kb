# Framework Specification

This is the maximal specification for the Expert Coordination framework — every directory, every file type, every capability, every rule. Bootstrap a new project via [SETUP.md](https://github.com/mrjames313/expert_kb/blob/main/SETUP.md); learn what's needed when from the [adoption guide](adoption-guide.md); reach for this document when you want the full reference.

A lightweight framework for orchestrating multi-area project development with Claude Code agents. Knowledge, code, and data are organized around shared project structures and area-specific structures, with disciplined paths for information to flow between them.

The framework is built around a small always-on foundation plus four togglable capabilities that can be enabled when their cost is justified by the project's signals.

---

## 1. Principles

The framework is built around five ideas, in priority order:

**Specialized areas build toward a shared goal.** A project's work splits across distinct knowledge domains — research, engineering, business model, product. Each area defines its own roles, operates with autonomy within its scope, and contributes back to the commons — the shared ground that holds the project's direction and distilled findings — through a defined promotion protocol. Path-based ownership is the mechanism: every file's location says who owns it.

**Specs precede work; replanning is normal.** Every substantive task — research, code, business model, customer study — starts with a brief and a plan. Phase gates exist so a human can correct course before effort is sunk. When reality diverges from the plan, agents replan via a documented step rather than silently drifting.

**Knowledge compounds; the wiki is the artifact.** The wiki is a persistent compounding artifact, not a transcript of chats. Findings, concepts, and decisions are filed as pages with lifecycle and provenance. The wiki layer (`kb/`) is distinct from the raw layer (`raw/`) — raw materials are immutable; the wiki is what compounds.

**Context loading is intentional.** What an agent loads is decided deliberately, not implicitly. Commons supplies the general background every role needs; frontmatter on each kb page declares relevance hints that guide what else to add. Agents read frontmatter first; full bodies load only when material to the task.

**Discipline scales with need.** A small always-on foundation handles the typical case; togglable capabilities add machinery (POR, subagents, formal review) when projects grow into needing them.

---

## 2. Directory layout

```
project-root/
├── README.md
├── CLAUDE.md                          # schema document — the operating manual
├── INBOX.md                           # human-attention items (async)
├── areas-index.md                     # lint-generated map of areas + roles
│
├── _framework/                        # all framework infrastructure
│   ├── spec.md                        # maximal specification (this document)
│   ├── adoption-guide.md              # how to start minimal and extend
│   ├── config.yml                     # current configuration
│   ├── schema/
│   │   ├── frontmatter.md
│   │   ├── link-conventions.md
│   │   ├── lint-rules.md
│   │   ├── index-format.md
│   │   ├── exchange-protocol.md
│   │   ├── promotion-protocol.md
│   │   ├── commons-extension-protocol.md
│   │   ├── role-template.md
│   │   ├── capabilities.md            # describes each togglable capability
│   │   ├── claude-snippets/           # per-capability CLAUDE.md sections
│   │   │   ├── multi_area.md
│   │   │   ├── por.md
│   │   │   ├── task_subagents.md
│   │   │   └── formal_review.md
│   │   └── spec-template/
│   │       ├── brief.md.tmpl
│   │       ├── plan.md.tmpl
│   │       ├── tasks.md.tmpl
│   │       ├── revisions.md.tmpl
│   │       └── outcome.md.tmpl
│   ├── tools/                         # deterministic helpers (python)
│   │   ├── lint.py
│   │   ├── lint_rules/                # one module per lint rule
│   │   ├── common.py                  # shared helpers
│   │   ├── pulse_compact.py
│   │   ├── promote.py
│   │   ├── commons_extension.py
│   │   ├── commons_links.py
│   │   ├── manifest_validate.py
│   │   ├── activity_days.py
│   │   ├── token_estimate.py
│   │   ├── telemetry.py
│   │   ├── framework.py
│   │   ├── framework_check.py          # hard-edge self-consistency checks (CI/pre-push)
│   │   ├── session_state.py            # _session/<id>.json read/write + transcript tokens
│   │   ├── kb_vitals.py                # /kb-vitals: state + next-actions scan
│   │   ├── vitals_cache.py             # snapshot of the expensive vitals (status line)
│   │   ├── statusline.py               # compact Claude Code status line (per render)
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   └── tests/
│   └── hooks/
│       ├── session-start.sh
│       ├── pre-compact.sh
│       └── session-end.sh
│
├── commons/                           # shared ground for all areas
│   ├── brief.md
│   ├── POR.md                         # only when capability: por is enabled
│   ├── pulse.md                       # current state, bounded
│   ├── _journal/
│   │   └── pulse.log                  # append-only events
│   ├── CHANGELOG.md
│   ├── _proposed/
│   ├── roles/
│   │   ├── coordinator/role.md        # only when capability: por is enabled
│   │   └── (other project-wide roles)
│   ├── kb/                            # essential, distilled findings
│   │   ├── index.md                   # lint-generated
│   │   ├── findings/
│   │   ├── decisions/
│   │   ├── concepts/
│   │   └── sources/
│   ├── raw/
│   ├── code/
│   └── data/
│       └── manifests/
│
├── areas/
│   └── <area>/
│       ├── brief.md
│       ├── POR.md                     # only when capability: por is enabled
│       ├── pulse.md
│       ├── _journal/
│       │   └── pulse.log
│       ├── roles/
│       ├── kb/
│       ├── raw/
│       ├── code/
│       ├── data/
│       └── specs/
│
├── exchanges/                         # exists when capability: multi_area is on
│   └── <a>--<b>/                      # areas sorted; a sub-area's slash flattens to -
│       ├── OWNERS
│       ├── README.md
│       ├── index.md                   # generated by lint (Rule 15)
│       └── ex-*.md
│
└── .claude/                           # claude code config (committed)
    ├── settings.json                  # hooks wired here
    └── skills/                        # agent skills
        ├── framework/SKILL.md
        ├── start/SKILL.md
        ├── ingest/SKILL.md
        ├── ask/SKILL.md
        ├── plan/SKILL.md
        ├── implement/SKILL.md
        ├── replan/SKILL.md
        ├── wrap-up/SKILL.md
        ├── check/SKILL.md
        ├── propose-promotion/SKILL.md
        ├── promote/SKILL.md
        ├── kb-vitals/SKILL.md
        └── (capability-gated skills, see section 15)
```

**Underscore convention.** A single `_framework/` directory holds all infrastructure. Project content has no underscore prefix (`commons`, `areas`, `roles`, `specs`, `kb`, `raw`, `code`, `data`, `exchanges`). Exceptions: `_proposed/` inside `commons/` (workflow artifact; "do not write directly"), `_journal/` per area (transient working records; written through skills, not by hand), and `_session/` at the repo root (git-ignored runtime state, **one file per session**: `_session/<session-id>.json` holds that session's adopted role/area, session id, transcript path, and context tokens; written by `/start` and the session-start hook, read by `/kb-vitals` and the status line). Sharding on the Claude session id keeps concurrent sessions in one repo — each with its own adopted role — from overwriting each other; consumers key on `$CLAUDE_CODE_SESSION_ID` (agent tools) or the `session_id` in their hook/status-line payload. Files from dead sessions are swept at session start.

**Areas nest.** Sub-specialties (e.g., `areas/research/optics/`) have the same internal shape as parents. Explicit inheritance — role files in the child explicitly reference parent paths in preload lists.

**Raw vs wiki.** Raw materials in `raw/` are immutable; agents read but never modify. The `source` page in `kb/sources/` is the structured summary, with frontmatter `provenance.raw_path` pointing back into `raw/`.

**Raw vs data.** Raw is documents and unstructured material (papers, transcripts, web clips); data is structured datasets with manifests in `data/manifests/`.

**Why `commons`.** The name captures jointly-stewarded shared ground — explicitly the resource the areas pool into and draw from. Direction flows down from commons to areas (brief, POR, mission); distilled findings flow up from areas to commons via the promotion protocol. The plural carries the bidirectional stewardship that a singular "common" couldn't.

### File maintenance categories

- **Human-authored (H)** — hand-edited; agents read but don't write.
- **Agent-maintained (A)** — agents read and write per protocol.
- **Lint-generated (L)** — auto-regenerated from other files; do not hand-edit.

Mapping:

| Path | Category |
|---|---|
| `README.md`, `CLAUDE.md` | H |
| `_framework/**` (schema, tools, hooks, spec.md) | H |
| `_framework/config.yml` | A (managed by `/framework` skill) |
| `.claude/settings.json`, `.claude/skills/**` | H |
| `commons/brief.md`, `areas/**/brief.md` | H |
| `commons/roles/**/role.md`, `areas/**/roles/**/role.md` | H |
| `exchanges/**/OWNERS`, `exchanges/**/README.md` | H |
| `INBOX.md` | A (agents append; human clears) |
| `commons/POR.md`, `areas/**/POR.md` | A |
| `**/pulse.md` | A |
| `**/_journal/pulse.log` | A |
| `commons/CHANGELOG.md` | A |
| `commons/_proposed/**` | A |
| `commons/kb/**/*.md` (post-promotion) | A |
| `areas/**/kb/**/*.md` | A |
| `areas/**/data/manifests/**` | A |
| `areas/**/specs/**` | A |
| `exchanges/**/ex-*.md` | A |
| `**/raw/**` | H (immutable; treated as if human-authored) |
| `areas-index.md` | L |
| `**/kb/index.md` | L |
| `exchanges/**/index.md` | L |
| `**/*.links.json` (backlink sidecars) | L |

These categories are a **convention agents uphold, not a boundary lint enforces** — no rule reads
this table, and a write outside it is silent. The model holds because agents follow it, and the
table is here to say who *should* write what, not to describe a check. Two entries are backed by
real machinery: `**/raw/**` by Rule 17 (raw immutability), and the `L` rows by regeneration —
lint rewrites them, so a hand edit is simply overwritten rather than flagged.

Where a case genuinely warrants writing outside your category, raise it in conversation and leave
a visible trace (`CHANGELOG.md`, an INBOX heads-up) instead of writing silently. Mechanical
enforcement of the `A`/`H` split is the deferred Rule 19, which needs git author signals to tell
an agent write from a human one.

---

## 3. Capabilities and the `/framework` command

The framework defines a small always-on foundation plus four togglable capabilities. Each capability can be independently enabled or disabled. State lives in `_framework/config.yml`. Changes happen via the `/framework` skill — never by hand-editing config.

### The four capabilities

| Capability | What it adds | Default |
|---|---|---|
| `multi_area` | Pairwise Q&A protocol between areas (the "exchanges" protocol), plus `exchange`, `respond-exchange`, `close-exchange`, `answer-from-kb` skills. | off |
| `por` | Plan of Record files per area and in commons, plus the coordinator role for cross-area planning. POR is loaded into every role's preload list. | off |
| `task_subagents` | Tasks within specs are executed by fresh subagents (clean context, role-loaded). Parent agent plans and orchestrates; subagents implement. | off |
| `formal_review` | Adds rigor on top of subagent execution: independent reviewer subagent after each task, auto-debug subagent on second rejection, and per-area verdict subagents for commons promotions. **Requires `task_subagents`.** | off |

### What's always on (the foundation)

These are not capabilities; they define what the framework is:

- Path-based ownership and the directory layout.
- Frontmatter discipline (the four types: source, concept, finding, decision; their lifecycles).
- CLAUDE.md as the schema document.
- Pulse discipline (per-area `pulse.md` + `_journal/pulse.log`; `wrap-up` compaction).
- Wiki/raw two-layer split.
- Lint correctness rules (always-on errors, see section 14).
- Single-human-gate promotion to commons (the *protection* is always on; `formal_review` adds per-area verdicts on top).
- Specs with phase gates and replanning.
- INBOX for asynchronous human attention; conversation as dominant interaction.

### The `/framework` command

A single skill provides all capability and lint-visibility management.

```
/framework                          show current state of all capabilities
                                    and lint visibility

/framework enable <capability>      enable a capability; prompts for approval,
                                    lists file changes, applies atomically

/framework disable <capability>     disable a capability; warns about content
                                    that becomes inert; applies atomically

/framework enable-lint <rule>       make a disabled lint warning visible

/framework disable-lint <rule>      stop displaying a lint warning
                                    (the rule still runs in shadow mode)

/framework lint-status              show which lint rules are visible vs shadow,
                                    plus recent shadow trigger counts

/framework prune [role]             analyze role file(s) for stale preload
                                    entries; surface candidates for removal
                                    in batched-approval flow

/framework resync                   re-splice enabled capabilities' content
                                    (CLAUDE.md sections + role-file # capability:
                                    blocks) from the current snippets; content
                                    only, no file create/delete or config change;
                                    run after an upgrade pulls new snippets

/framework update                   pull the latest framework: fetch and follow
                                    the canonical UPGRADING.md (not a framework.py
                                    command)
```

The skill's behavior on `enable`:

1. Reads `config.yml`. If already enabled, no-op.
2. Checks dependencies. If `formal_review` requested without `task_subagents`, offers to enable both.
3. Lists proposed file changes in conversation:
   - Files created (e.g., `POR.md` per area when enabling `por`).
   - Files edited (which sections of CLAUDE.md are added, which role files get updated, which skills come online).
4. After user approval (in conversation), applies all changes atomically.
5. Updates `config.yml`.
6. Runs `/check` to confirm clean lint state.

The skill's behavior on `disable`:

1. Identifies content that will become inert (e.g., POR.md files when disabling `por`, exchange files when disabling `multi_area`). Files are **not deleted** — they remain on disk but stop being referenced by role preload lists, schema document sections, and skill behaviors.
2. Warns the user in conversation if substantial content exists.
3. After approval, removes the relevant CLAUDE.md sections, role file entries, and skill conditionals.
4. Updates `config.yml`.
5. Re-enabling later picks up the existing files where they were.

The skill's behavior on `prune`:

1. Reads telemetry data for the targeted role(s) — defaults to all roles if no role specified.
2. For each role, identifies stale preload entries:
   - **Full-tier**: pages not cited or body-loaded in the last `prune.full_tier_stale_sessions` active sessions (default 10).
   - **Frontmatter-tier**: patterns whose matched files yielded no body-loads in the last `prune.frontmatter_tier_stale_sessions` active sessions (default 30). Frontmatter is cheaper to load so the threshold is higher.
   - Pages whose `status` has moved to `superseded`, `dropped`, or `falsified`, regardless of cite history.
3. Surfaces all candidates in conversation with rationale for each.
4. Accepts batched user approval (per-candidate Y/N, or "accept all," or "skip all").
5. Applies approved removals to role files atomically.
6. Runs `/check` to confirm clean lint state.

Pruning never deletes the underlying kb pages — only their entries in role preload lists.

The skill's behavior on `update`: it does not touch `framework.py`. It adds the framework repo as a git remote, fetches, reads the latest `UPGRADING.md` from it, and follows those instructions — which gate on a clean, committed tree (so the upgrade is reversible), pull framework files (never project content or `config.yml`), reconcile CLAUDE.md by hand, run migrations keyed to the project's `framework_version`, and verify with lint. The canonical procedure lives upstream, so an outdated local skill still upgrades correctly.

Capability-specific change lists are described declaratively in `_framework/schema/capabilities.md`. The `framework` skill reads this file and applies the described edits. Adding a new capability later means a new section in `capabilities.md` plus a handler in `framework.py`.

### `config.yml` shape

```yaml
# _framework/config.yml

framework_version: 2026-08-15   # illustrative; the live value in _framework/config.yml is authoritative, bumped on each framework upgrade

capabilities:
  multi_area: false
  por: false
  task_subagents: false
  formal_review: false

lint:
  # thresholds (apply regardless of warning visibility)
  pulse_line_cap: 80
  stale_concept_threshold_active_days: 30
  promotion_freshness_active_days: 14
  spec_abandonment_active_days: 60
  exchange_stale_active_days: 7
  cross_area_link_threshold: 3
  recent_decisions_window_active_days: 7

  # threshold for suggesting that a shadow rule be enabled
  shadow_suggest_threshold: 5

  # which warning rules are visible (false = self-gated / shadowed).
  # One key per *shipped* warning rule; /framework enable-lint derives its
  # accepted set from the rule modules, so planned-but-unimplemented rules
  # (4/8/9/10/11/13/14/16) are not listed until they ship.
  warnings_visible:
    rule_20_commons_drift: false
    rule_21_commons_twin_links: false

prune:
  # thresholds for /framework prune analysis (in active sessions)
  full_tier_stale_sessions: 10
  frontmatter_tier_stale_sessions: 30
```

Lint, hooks, and skills read from `config.yml` at runtime. Conditional behavior (e.g., does `/implement` spawn a subagent?) checks the relevant capability flag.

---

## 4. The schema document (CLAUDE.md)

CLAUDE.md contains operating principles. It's reshaped by `/framework enable` and `/framework disable` to reflect only currently-enabled capabilities. The current capability set is always visible in `_framework/config.yml`; CLAUDE.md reflects state, not options.

Capability-gated sections are inserted from corresponding files in `_framework/schema/claude-snippets/`. The `framework` skill reads the snippet file and splices it into CLAUDE.md at a marker position (between always-on sections, before "Escalation triggers").

Always-present sections:

```
# Project operating manual

## What this project is
## How knowledge is organized
## How to start a session
## Communicating with the human
## When to write where
## How to interpret types
## Frontmatter discipline
## Loading context
## Links and provenance
## Pulse discipline
## Suggesting preload updates
## Spec lifecycle
## Skills
## Escalation triggers
```

Capability-gated sections (snippet source in `_framework/schema/claude-snippets/`):

```
## Cross-area reads                    (capability: multi_area)
## POR discipline                      (capability: por)
## Subagent pattern                    (capability: task_subagents)
## Formal review                       (capability: formal_review)
```

The "Communicating with the human" section is always present and frames conversation as the dominant interaction mode, with INBOX supplementary for asynchronous attention.

The trim from prior iterations: details on concept stages, type-specific handling, and link mechanics now live in `_framework/schema/frontmatter.md` and `_framework/schema/link-conventions.md`. CLAUDE.md references these but doesn't duplicate them. New procedural sections — "Frontmatter discipline," "Suggesting preload updates," "Pulse discipline" (with log format), and an expanded "Spec lifecycle" (with replan rule of thumb) — replace the trimmed content.

---

## 5. Frontmatter spec

Four types (`source`, `concept`, `finding`, `decision`); status lifecycles per type; type-specific fields; commons-promoted items carry `human_reviewed`, `promoted_from`, `promoted_on`. Source provenance carries `raw_path` pointing into `raw/`. Lint sidecars for backlinks.

See `_framework/schema/frontmatter.md` for the full specification — including the **frontmatter discipline** section that covers when frontmatter gets written or updated, across all creation paths (`/ingest`, `/ask` synthesis, in-conversation idea capture, `/wrap-up` materialization, `/promote`).

### Preload-update suggestion mechanism

When an agent creates or substantively updates a notable page (high-confidence finding, decision, frequently-cited concept), the agent evaluates whether the page should be in some role's preload list. Criteria:

- Type is `finding` with `confidence: high`, OR
- Type is `decision` (active), OR
- Type is `concept` with `status: supported` or actively-cited `under_test`.

If the page qualifies, the agent files an INBOX entry under "Heads up":

> **Preload suggestion**: Consider adding [[<page>]] to `<role-file-path>` (full | frontmatter tier). Reason: <one-line rationale>.

The human reviews and either accepts (agent edits the role file with explicit human confirmation in conversation since role files are human-authored) or declines. Declined suggestions are tracked in `_framework/telemetry/dismissed-suggestions.jsonl` so they're not repeated.

The `/wrap-up` skill scans pages created or updated during the session and files suggestions as a final step before lint.

### Preload pruning

The complementary mechanism. Where the suggestion mechanism handles **additions** (proactively, per-page during work), pruning handles **removals** (cross-session analysis, run on demand).

Pruning identifies candidates from three sources:

- **Stale full-tier entries** — pages in a role's full preload not cited or body-loaded in the last `prune.full_tier_stale_sessions` active sessions (default 10).
- **Stale frontmatter-tier patterns** — patterns whose matched files yielded no body-loads in the last `prune.frontmatter_tier_stale_sessions` active sessions (default 30). Frontmatter is cheaper, so the threshold is higher.
- **Lifecycle-driven removals** — pages whose `status` has moved to `superseded`, `dropped`, or `falsified`, regardless of cite history.

Three paths to act on candidates:

- **Passive surfacing** — `/budget` includes a "Recommended prunes" section in its routine report.
- **Explicit analysis** — `/framework prune [role]` runs the full analysis, surfaces candidates with rationale, and accepts batched approval (per-candidate Y/N, "accept all," or "skip all"). When the user runs prune explicitly, they want a contained back-and-forth.
- **Reactive cleanup** — when a kb page's status transitions to `superseded`/`dropped`/`falsified`, the framework files an INBOX "Heads up" pointing to any role files that reference it.

Pruning never deletes the underlying kb pages — only their entries in role preload lists. Restoring an entry later is a normal role-file edit.

The telemetry data that makes pruning possible — citation tracking and body-load tracking per session — is captured by `_framework/tools/telemetry.py`; see section 18.

---

## 6. Role files

Role files are reshaped by `/framework enable` and `/framework disable` to reflect enabled capabilities. They use a **two-tier preload** structure:

- **Full preload** — small, curated; bodies are loaded into the agent's context.
- **Frontmatter preload** — broad; only frontmatter blocks from matching files are loaded. Specified as directory patterns.

The agent's session-start context is "full preload bodies + frontmatter blocks from files matching the frontmatter preload patterns." Bodies of other pages get loaded on demand when material to the work at hand.

The general shape:

```markdown
---
role: optics-researcher
area: research/optics
summary: Investigates optical-domain questions; designs and runs experiments;
         maintains the optics kb.
---

# Optics Researcher

## Preload context (full)

Schema and conventions:
1. /CLAUDE.md
2. /_framework/schema/frontmatter.md
3. /_framework/schema/link-conventions.md

Project and parent area:
4. /commons/brief.md
5. /commons/pulse.md
6. /commons/POR.md                              # only if capability: por
7. /areas/research/brief.md
8. /areas/research/pulse.md
9. /areas/research/POR.md                       # only if capability: por

Own area:
10. /areas/research/optics/brief.md
11. /areas/research/optics/pulse.md
12. /areas/research/optics/POR.md               # only if capability: por
13. /areas/research/optics/kb/index.md

## Preload context (frontmatter only)

Patterns — frontmatter blocks of all pages under these paths:
- /commons/kb/findings/
- /commons/kb/decisions/
- /areas/research/optics/kb/

Optional individual additions:
- /areas/research/kb/findings/   # parent-area findings

## Operating boundaries

- Writes allowed: /areas/research/optics/** EXCEPT /areas/research/optics/raw/**.
- Raw materials anywhere are read-only; existing files immutable. New raw materials added through /ingest.
- Writes to /commons/: not directly. New content via /propose-promotion; corrections to an existing commons page via /amend-commons (light gate).
- Writes to other areas: avoid — use /exchange to hand work across. The `commons_twin` back-pointer is the one sanctioned exception.
- Reads allowed: full repo; occasional cross-area reads are fine, but prefer /exchange (when available) over repeated deep reads into other areas' kb.

## Allowed skills

(set varies by enabled capabilities — see section 15)

## Default behaviors

- Cite using [[wikilinks]].
- When citing a concept, surface its status.
- When ending a session, run /wrap-up before clearing.
- When a task's plan looks wrong, invoke /replan; do not improvise.
- When you create or substantively update a notable page, file an INBOX "Heads up" preload suggestion if appropriate.
- Ask the human in conversation when uncertain. INBOX is for items the human will see later, not a substitute for asking now.
```

The `start` skill, when loading a role, processes the frontmatter preload patterns: for each pattern, recursively find all `.md` files in matching directories; extract only the frontmatter block (content between the leading and closing `---`); append each block to the agent's context with the file path as reference.

A **reviewer role** is a stripped-down variant of the implementer role. Same preload (both tiers); operating boundaries restricted to verdict files; allowed skills limited to `review`. Reviewer roles only exist when `formal_review` is enabled.

The **coordinator role** at `commons/roles/coordinator/role.md` exists only when `por` is enabled. Read-broad, write-narrow:
- **Full preload**: `CLAUDE.md`, schema files, `commons/brief.md`, `commons/POR.md`, `commons/pulse.md`, `areas-index.md`, `INBOX.md`, all area `POR.md` and `pulse.md` files.
- **Frontmatter preload**: all area `kb/` directories.
- **Writes**: `INBOX.md`, `commons/POR.md`, specs across areas. Cannot write area kb or commons kb.

See `_framework/schema/role-template.md` for the canonical template and `_framework/schema/index-format.md` for the `kb/index.md` format that the frontmatter preload complements.

---

## 7. Session start and role routing

SessionStart hook loads `CLAUDE.md`, `areas-index.md`, `INBOX.md`. The `start` skill handles routing — identifies area and role, loads preload list, or asks for clarification.

When `coordinator` role is unavailable (i.e., `por` is off), cross-area requests prompt the human in conversation to pick an area rather than auto-adopting a coordinator role.

Explicit invocation: `/start <role> <request>` skips the routing and adopts the named role directly.

The `start` skill recognizes three patterns for in-request routing beyond the default content-based inference: (1) **inline area or role mentions** ("…in engineering", "as a researcher…") parsed and used directly without further prompting; (2) **mid-session switch language** ("switch to engineering", "now work as product-manager") that reloads the named role's preload list; and (3) **read-only cross-area queries** ("what's in engineering's pulse?") that keep the current role active and read the requested content without switching. Role switches happen only when the work would require writes outside the current role's boundaries.

**areas-index.md** is auto-maintained by lint. Format:

```markdown
# Areas Index
_Auto-maintained by lint; do not edit by hand._
_Last updated: 2026-05-08_

## commons/
Project-wide knowledge, code, and data. Use exchanges or area work,
not direct commons writes.

Roles:
- coordinator — cross-area planning, INBOX management, POR updates
  (only present when capability: por is enabled)

## areas/research/
[summary from areas/research/brief.md]

Roles:
- researcher — broad research questions

### areas/research/optics/
[summary from areas/research/optics/brief.md]

Roles:
- optics-researcher — optical-domain investigations
```

### Adding a new area or sub-area

The `/add-area <path>` skill walks the human through area creation. The path syntax handles both top-level areas (`/add-area engineering`) and sub-areas (`/add-area research/optics`). The skill:

1. Verifies the parent path exists and the target doesn't.
2. Asks the user (in conversation): brief description of the area's focus.
3. Creates the directory structure (`kb/`, `raw/`, `data/`, `specs/`, `roles/`, `_journal/`).
4. Writes `brief.md` (from user response), initial `pulse.md` template, empty `_journal/pulse.log`, empty `kb/index.md`.
5. Asks: what role(s) should this area have? Suggests defaults based on the parent area (e.g., for `research/optics`, suggest `optics-researcher`).
6. For each role, prompts the user to confirm or adjust the preload list (both tiers); creates the role file using `_framework/schema/role-template.md`.
7. Checks parent-area role files: if the parent has roles whose preload patterns should now reference the new sub-area, surfaces suggestions in conversation. Applies updates after human confirmation.
8. Runs lint to regenerate `areas-index.md` and confirm clean state.
9. Commits the new area.

If `por` is enabled, the skill also offers to create a stub `POR.md` for the new area.

---

## 8. POR (Plan of Record) — capability: `por`

When `por` is enabled, every area (and commons) has a `POR.md` file alongside `brief.md`. The three files complement each other:

- **brief.md** — why this exists. Changes rarely. Always present.
- **POR.md** — current plan and execution state. Updated when phases shift, workstreams change, or replans happen. Present only when `por` is enabled.
- **pulse.md** — what's current. Changes constantly. Always present.

POR content includes current phase, active workstreams, upcoming, dependencies, and status/risks.

The `wrap-up` skill prompts the user in conversation to confirm POR updates when relevant events occurred during the session.

The `coordinator` role exists when `por` is enabled and updates `commons/POR.md`. Area roles update their own area's POR.

**On disable.** Existing POR files remain on disk. Role preload lists are updated to remove POR references; CLAUDE.md's POR section is removed; the coordinator role file is removed from `commons/roles/`. Re-enabling later picks up the existing files where they were.

---

## 9. INBOX

`INBOX.md` at the project root collects items that need the human's attention asynchronously. Three sections (Needs decision, Awaiting your ack, Heads up). Agents append; human clears. Conversation remains the dominant interaction mode; INBOX is supplementary.

```markdown
# Inbox
_Last touched by agents: 2026-05-08 14:22_

## Needs decision
(blocked on you; agents cannot proceed)

- [2026-05-07] Objection on proposed promotion
  `commons/_proposed/2026-05-07-noise-finding/`. Engineering objects to scope;
  research approves. Verdict files in proposal dir.

- [2026-05-06] Spec `specs/2026-05-1f-noise` brief drafted in
  areas/research/optics/; awaiting your approval before plan phase.

## Awaiting your ack
(done, just needs your eyes)

- [2026-05-08] Promoted to commons: [[findings/f-2026-05-shot-noise]]
  (human_reviewed: false).

## Heads up
(FYI; you don't need to act, but you should know)

- [2026-05-08] 5 customer interview transcripts in `areas/product/raw/interviews/`
  not yet ingested.
- [2026-05-08] Exchange `engineering--research/q-2026-05-04-thermal` open
  for 4 active days without response.
```

---

## 10. Spec template

Every substantive task lives in a spec directory under `<area>/specs/<date>-<slug>/`:

```
specs/2026-05-photodetector-noise/
├── brief.md         # what we're doing and why; one screen
├── plan.md          # method, architecture, or approach
├── tasks.md         # discrete steps with _Boundary:_ and _Depends:_
├── revisions.md     # append-only log of replans
└── outcome.md       # what happened; produced pages; superseded plans
```

Per-task annotations:

```markdown
### T1: Set up the noise-floor measurement rig
_Boundary:_ /areas/research/optics/code/measurement-rig/
_Depends:_ —
_Status:_ planned
_Owner role:_ optics-researcher

[task description]

#### Implementation Notes
(Appended by subagents as they work; persists across sessions.)
```

Phase gates: brief → [human approves in conversation] → plan → [human approves] → tasks → execution → outcome → [human approves close]. `/replan` can fire from any point; appends to `revisions.md`; updates plan and/or tasks.

When `task_subagents` is off, `/implement` runs the work in the current agent. When on, each task spawns a fresh subagent.

---

## 11. Pulse mechanics

Each area, sub-area, and commons maintains a pair of files:

**pulse.md** — canonical current state, bounded. Maximum size enforced by lint (default 80 lines). Sections:

```markdown
# Research/Optics — pulse
_Last compaction: 2026-05-08 14:30_

## Current focus
(2–4 lines, rewritten not appended)

## Recent decisions (last 7 active days)
- [[decisions/d-2026-05-04-bias-current]] — bias at 1 mA, not 5 mA
- ...

## Active concepts under test
- [[concepts/c-2026-04-shot-noise]] — status: under_test
- ...

## Open questions
- Does 1/f noise floor depend on bias direction?
- ...

## Recent findings (last 5)
- [[findings/f-2026-05-shot-noise]]
- ...
```

**_journal/pulse.log** — append-only event log; new entries go at the **bottom**, so timestamps are non-decreasing top-to-bottom. `/wrap-up` (via `pulse_compact.py`) warns if an entry's timestamp is earlier than the one above it — the usual sign an agent prepended instead of appending. Entries during the session:

```markdown
## [2026-05-08 09:14] decision optics-researcher
Adopted bias current of 1 mA per measurement constraints.
→ to be filed: decisions/d-2026-05-04-bias-current

## [2026-05-08 11:22] finding optics-researcher
Shot noise floor measured at 1310nm; matches theory within 8%.
→ to be filed: findings/f-2026-05-shot-noise

## [2026-05-08 13:45] focus-shift optics-researcher
Switching from noise-floor characterization to 1/f investigation per replan
in spec ...
```

The `_journal/` subdirectory holds transient working records — currently just `pulse.log`, but a natural home for any future append-only artifacts (debug traces, session histories) that agents produce during work and that get compacted or truncated later.

**Compaction (the `wrap-up` skill)**:

1. Read `_journal/pulse.log` and `pulse.md`.
2. For each log entry, decide:
   - **decision**: ensure a `decisions/` page exists; reference in "Recent decisions"; drop entries past activity-day threshold.
   - **finding**: ensure a `findings/` page exists; keep 5 most recent in pulse.
   - **concept**: update "Active concepts under test" with status changes.
   - **question**: add to "Open questions" if novel; remove when resolved.
   - **focus-shift**: rewrite "Current focus."
3. Verify `pulse.md` fits the line cap. If not, promote oldest items to kb or drop — never silent truncation.
4. If POR-affecting events occurred and `por` is enabled, prompt the user in conversation to confirm POR updates and apply them.
5. Truncate `_journal/pulse.log`.
6. Run lint.
7. Commit (optional; on by default).

**Compaction triggers**:
- Manual: `/wrap-up` invoked by user before session end or context clear.
- Hooks: `PreCompact` and `SessionEnd` invoke wrap-up as a safety net — but only where hooks are active (they are read at process start; see `_framework/hooks/README.md`), so this is a backstop, not a guarantee.

A session that ends without `/wrap-up` and without hooks firing leaves a stale log. Next session's first read of pulse should detect a non-empty log and either compact first or surface a warning.

---

## 12. Exchange protocol — capability: `multi_area`

Exchanges are how areas communicate across boundaries without deep-reading each other's kb. An exchange has a **kind**: `query` (pull — area X asks area Y an authoritative question) or `brief` (push — area X hands a conclusion to specific role(s) in area Y, no responder obligation). Both share the directory, index, `from`/`to` identifiers, and persistence; they differ in lifecycle. Full detail in `_framework/schema/exchange-protocol.md`.

**Filing.** `/exchange <other-area> <text> [--kind query|brief]` (default `query`). Creates `exchanges/<a>--<b>/` (with `OWNERS` and `README.md`) if absent and writes `<id>.md`. Parties are named neutrally: `from_area`/`from_role` (filer), `to_area` (receiving area), and — briefs only — `to_roles` (targeted roles, snapshot at file time).

**Directory naming.** The two areas sorted alphabetically and joined by `--`; a sub-area's slash flattens to `-` (`to_area: research/optics` → `exchanges/engineering--research-optics/`). Every consumer globs one level (`exchanges/*/`), so a nested directory would make the exchange invisible rather than invalid. Rule 22 checks the file sits in its pair's canonical directory.

**The index.** `exchanges/<a>--<b>/index.md` is regenerated by lint (Rule 15) from the exchange files' frontmatter, grouped by status with open first, entries as relative markdown links — exchanges aren't in the wikilink index, so the `[[<id>]]` form the protocol once specified could never resolve. No skill hand-edits it.

**Lint coverage.** Rules 2 and 5 walk exchange files: their `## Context` wikilinks must resolve, a present area prefix must be right, and a link to a superseded page is an error. Exchange frontmatter is a different schema from a kb page's, so Rule 22 validates it rather than Rule 1.

```yaml
---
id: ex-2026-05-08-drift-model-update
kind: brief
status: open                 # query: open|answered|follow_up|closed.  brief: open|closed
from_area: research
from_role: optics-researcher
to_area: engineering
to_roles: [hardware-engineer, firmware-engineer]   # brief only
open_for: [hardware-engineer, firmware-engineer]   # brief only; drained on disposition
created: 2026-05-08
---
# Brief
The drift model now predicts ~2x the responsivity swing at 85 C.
## Context
[[research:findings/f-2026-05-drift-model]]
# Dispositions
(each targeted role records what it did)
```

**Query lifecycle.** Responder invokes `/respond-exchange <id>` (spawns a role-context subagent when `task_subagents` is on; may use `/answer-from-kb`); status flips to `answered`. The asker reviews and closes via the disposition step.

**Brief lifecycle.** No responder obligation. Each role in `to_roles` disposes independently (`/close-exchange`), recording a `# Dispositions` entry and dropping itself from `open_for`; status flips to `closed` when `open_for` is empty. `open_for` is frozen — new roles catch up via the deferred `/add-role`. Declining is an explicit `none`.

**Disposing (close).** The party that received information disposes and closes — the asker for a query, each targeted role for a brief. Options: **preload** the referenced page into the disposing role's `role.md`, **file/cite** it in that role's kb, or **none**.

**Surfacing.** `/start` scans `exchanges/*/` for the adopted role and surfaces open queries to answer, answered queries to close, and briefs where the role is still in `open_for`. Staleness lint flags open queries and briefs with a non-empty `open_for` to INBOX.

**On disable.** Existing exchange directories remain, and lint keeps their indexes regenerated and their links checked. Skills become unavailable; CLAUDE.md's "Cross-area reads" section is removed. Re-enabling picks up existing exchanges.

---

## 13. Link conventions

Within `kb/` directories, agents use Obsidian-style `[[wikilinks]]`. For files outside `kb/` (code, manifests, specs, raw materials), agents use relative markdown links with explicit paths.

**Forward links** are written by the authoring agent. **Backlinks** are maintained by the linter via sidecar `<page>.links.json` files. The author never edits the sidecar.

**Linking to superseded pages is an error.** The linter suggests the replacement via `superseded_by`.

**Cross-area links are valid but watched.** Lint warns when a single page accumulates links to multiple distinct areas (default 3+). Pages with `area: commons` are exempt.

**Cross-area links may carry an `area:` prefix** naming the target's area — `[[engineering:findings/f-...]]`, `[[commons:...]]`, nested `[[research/optics:...]]` (split on the first colon). The prefix is a readability aid; resolution doesn't require it (ids are project-unique). Rule 2 errors if a present prefix doesn't match the target's actual area.

**Bidirectional content consistency** requires both lint and convention:

- **Lint (Rule 13)**: flag pages whose `links_out` point to pages updated more recently than the page itself. Output goes to INBOX or `/check` summary.
- **Convention** (in CLAUDE.md): after substantively updating a page, agents check the page's backlinks. For each backlinker, the agent decides whether the update affects what the backlinker asserts. If yes, the agent updates the backlinker inline (preferred) or files an INBOX "Heads up" entry.

---

## 14. Lint rules

The linter (`_framework/tools/lint.py`) is deterministic Python. It runs on demand via `/check` and at the end of every `/wrap-up`.

**Always-visible rules always run.** Configurable-visibility (warning) rules are off by default and currently **self-gate** — a disabled rule returns no findings; enable it with `/framework enable-lint <rule>`.

**Always-visible rules** (errors and structural correctness):

```
Rule 1.  Frontmatter validity.
Rule 2.  Forward-link integrity (body + frontmatter wikilinks, area prefixes, provenance.raw_path).
         Scope: kb pages, spec planning files, data manifests, exchange files.
Rule 3.  Backlink synchronization.
Rule 5.  Supersession integrity.
Rule 6.  Type-specific completeness.
Rule 7.  Pulse size (pulse.md exceeding line cap is an error).
Rule 12. Data manifest integrity.
Rule 15. Index maintenance (regenerate areas-index.md, kb/index.md, exchanges/*/index.md).
Rule 17. Raw immutability (modifications to existing files in raw/ — additions are allowed).
Rule 18. Page ID uniqueness across the project.
Rule 22. Exchange frontmatter validity (kind, per-kind status vocabulary and required fields,
         open_for ⊆ to_roles, closed ⟺ open_for empty, id/filename agreement, canonical directory).
```

**Configurable-visibility rules** (warnings):

```
Rule 4.  Orphan detection.
Rule 8.  Stale concept warning (concept: under_test > 30 active days).
Rule 9.  Cross-area link threshold (>= N areas; commons pages exempt).
Rule 10. Promotion freshness (human_reviewed: false > 14 active days).
Rule 11. Spec hygiene (tasks non-terminal > 60 active days).
Rule 13. Backlinker freshness.
Rule 14. Exchange staleness (status: open > 7 active days, if multi_area on).
Rule 16. Cross-area read pattern.
Rule 20. Commons drift (source updated after the commons page's aligned_on; also flags any commons page it cannot drift-check — missing aligned_on/promoted_from_page — rather than skipping it silently).
Rule 21. Commons twin-link preference (commons page cites an area page that has a twin).
```

**Shadow behavior (not implemented; under reconsideration).** The original design had disabled rules run silently, accumulate trigger counts, and surface a "consider enabling" suggestion past `shadow_suggest_threshold`. That isn't built — warning rules self-gate instead — and it may be dropped as noise-without-value. Rules 10, 20, and 21 are the implemented members of the configurable set; the shadow decision remains open in the framework repo's backlog.

**Activity-based thresholds.** All time thresholds use git-log-derived active days, computed via `_framework/tools/activity_days.py`.

**Capability-conditional rules.** Rule 14 (exchange staleness) only runs when `multi_area` is enabled. Rules 2, 5, 15 and 22 touch exchanges but are *not* gated: exchange directories survive disabling the capability, and an index or a link check that silently stopped applying to files still on disk would be worse than one kept honest. Absent an `exchanges/` directory they are no-ops.

The linter is the trust anchor. No LLM in the loop.

---

## 15. Skills

Each skill is a Claude Code Agent Skill with a `SKILL.md`. Skills can be invoked explicitly by slash command or autonomously when context matches the skill's trigger conditions.

**Always available:**

| Skill | Purpose |
|---|---|
| `framework` | Manage capabilities and lint visibility. |
| `start` | Route a fresh session: identify area, suggest role, load preload list. |
| `ingest` | Store raw material in `raw/`; create source summary in `kb/sources/` with provenance; link to concepts. |
| `ask` | Query the wiki; synthesize an answer; optionally file as kb page. |
| `plan` | Bootstrap a spec: brief → plan → tasks (human gates in conversation). |
| `implement` | Execute one task. Behavior depends on `task_subagents`. |
| `replan` | Append revision entry; update plan and tasks; require human approval. |
| `propose-promotion` | Copy area page to `commons/_proposed/`; generate proposal; register in INBOX. |
| `promote` | Apply promotion after consensus or human override; write CHANGELOG entry. Behavior depends on `formal_review`. |
| `amend-commons` | Edit an existing commons page in place (correction, link rewrite, drift reconciliation); light-gated + CHANGELOG entry. |
| `wrap-up` | Compact `_journal/pulse.log` → `pulse.md`; file pending pages; prompt POR updates (if `por` on); run lint. |
| `check` | Run lint; display findings; surface shadow-rule suggestions. |
| `budget` | Report estimated context cost of role preloads and recent session telemetry; identify heavy paths and pruning candidates. |
| `add-area` | Walk the human through creating a new area or sub-area: directory structure, brief, pulse template, roles, and any parent-area role file updates. |
| `kb-vitals` | Scan operational state → next actions: human vitals (decisions/acks, project-wide) + role vitals (current area hygiene, incl. a stale/bloated-session restart nudge). Reads this session's `_session/<session-id>.json`; runs no lint. |

**Capability-gated:**

| Skill | Available when |
|---|---|
| `exchange` | `multi_area` on |
| `respond-exchange` | `multi_area` on |
| `close-exchange` | `multi_area` on |
| `answer-from-kb` | `multi_area` on |
| `review` | `formal_review` on |
| `review-promotion` | `formal_review` on |

---

## 16. Promotion-review protocol

The always-on protection is a human gate on every commons change, in one of two forms: **new content** enters through `commons/_proposed/` and `/promote`; an **existing commons page** is corrected in place through `/amend-commons`, under a lighter gate (human confirmation in conversation plus a `CHANGELOG.md` entry). Neither path is a silent write.

**Without `formal_review`.** Filing happens via `/propose-promotion`. The human reads the proposal (often in conversation, or via INBOX). The human approves or rejects. On approval, `/promote` applies the change.

**With `formal_review`.** After filing, `/review-promotion` spawns a subagent in each other area's reviewer role. Each subagent writes `verdict-<area>.md` with `APPROVE | OBJECT | ABSTAIN` plus rationale. Consensus rules apply: all non-abstain APPROVE → auto-promote; any OBJECT → human escalation; all ABSTAIN → human decides. The human still acks (`human_reviewed: true`) after promotion.

In both cases, audit trail (`_proposed/` directory, verdict files when applicable) is kept after promotion.

---

## 17. Subagent pattern — capability: `task_subagents`

When `task_subagents` is enabled, `/implement` spawns a fresh subagent for each task. The subagent's context is loaded from the role's preload list — it does not see the parent's working context.

**Without `formal_review`.** The subagent executes the task. The parent agent (or the human) reviews the output in conversation. No reviewer subagent.

**With `formal_review`.** After the subagent completes, `/review` spawns a reviewer subagent in a reviewer role variant. The reviewer reads the output against the spec and writes a verdict. On rejection, parent may re-invoke `/implement` with rejection notes (retry limit default 2). On second rejection, an auto-debug subagent loads in clean context to investigate root causes.

Subagents don't parallelize automatically, don't carry state between invocations except via files, and don't override role boundaries.

**On disable.** `/implement` switches back to running in the current agent. No content loss.

---

## 18. Token instrumentation and budget tracking

The framework tracks per-session context cost so role preloads can be tuned and heavy paths identified. The mechanism is approximate but stable enough for comparison and pruning decisions.

### What Claude Code provides natively

Two interactive slash commands give exact, real-time visibility:

- **`/context`** — breaks down current context usage by category (system prompt, system tools, MCP tools, custom agents, memory files, skills, messages, free space, autocompact buffer) within Claude Code's 200k token window.
- **`/usage`** (aliases `/cost`, `/stats`) — session cost, plan usage limits, activity stats.

These are the source of truth at any given moment. The framework's job is to make preload costs **predictable** ahead of time and to surface trends across sessions.

### Framework instrumentation

**`_framework/tools/token_estimate.py`** estimates the token cost of a role's preload list (full bodies + frontmatter blocks from matching patterns) using a tokenizer compatible with Claude's model. The estimate is approximate but consistent enough for relative comparison across roles and over time.

**`_framework/tools/telemetry.py`** writes a per-session entry to `_framework/telemetry/sessions.jsonl`. The SessionStart hook records the preload estimate; the session-end hook (or `/wrap-up`) records what happened during the session. Each entry:

```json
{
  "timestamp": "2026-05-08T09:14:00Z",
  "session_id": "2026-05-08-am-optics",
  "role": "optics-researcher",
  "area": "research/optics",
  "full_preload_files": 13,
  "full_preload_tokens_est": 8450,
  "frontmatter_preload_files": 47,
  "frontmatter_preload_tokens_est": 3200,
  "total_preload_tokens_est": 11650,
  "pages_cited": [
    "areas/research/optics/kb/findings/f-2026-05-shot-noise.md",
    "areas/research/optics/kb/sources/s-2026-04-saleh-teich-ch17.md"
  ],
  "bodies_loaded_beyond_preload": [
    "areas/research/optics/kb/concepts/c-2026-04-1f-noise-bias.md"
  ]
}
```

The `pages_cited` and `bodies_loaded_beyond_preload` lists are **reported by the agent** at `/wrap-up`, which passes them to `telemetry.py session-end` as `--cited` and `--loaded`. They are best-effort recollection, not instrumentation: nothing scans outputs or hooks file-read tool calls, and the `wrap-up` skill says so explicitly. Read the data as a trend signal — which preloads go unused across many sessions — never as an exact per-session count.

The telemetry directory is git-ignored — entries are local to each clone.

### The `/budget` skill

Reports recent session telemetry and identifies pruning candidates:

- **Preload cost** — per-role average over the last N sessions, with 95th-percentile high-water mark.
- **Heaviest full-tier files** — candidates for moving to frontmatter tier or dropping.
- **Frontmatter patterns that match many files but rarely yield body-loads** — candidates for narrowing.
- **Recommended prunes** — pages stale per the prune thresholds (see section 5), filterable by role. Same data feeds `/framework prune` for the explicit-approval flow.
- **Budget comparison** — if a per-role `budget_tokens_est` is set in the role file's frontmatter, sessions exceeding it surface here.

The skill produces a brief report; the human decides whether to revise role files (manually or via `/framework prune`).

### Per-role budget targets

Optionally, role files can declare a budget target in frontmatter:

```yaml
---
role: optics-researcher
area: research/optics
summary: ...
budget_tokens_est: 12000
---
```

When set, `/budget` and `/check` flag sessions where estimated preload exceeded the target by a configurable margin.

### Subagent budgets

When `task_subagents` is enabled, each subagent invocation gets its own telemetry entry. Subagents typically use the same role's preload, so cost-per-task is predictable. The `/budget` skill aggregates subagent invocations separately from parent agent sessions.

---

## 19. Raw materials and data manifests

Raw materials in `raw/` are immutable; source pages in `kb/sources/` summarize them with `provenance.raw_path` pointing to the raw file. Data manifests in `data/manifests/` describe datasets; structured input data lives in `data/`.

Manifest example:

```markdown
---
id: m-2026-05-photodetector-noise-run3
title: Photodetector noise floor measurements, run 3
type: source
area: research/optics
created: 2026-05-04
storage_uri: s3://...
schema_uri: ../schemas/noise-floor-v1.json
provenance:
  kind: internal-experiment
  acquired_on: 2026-05-04
  instrument: Keysight DSOX1204G + custom TIA board v0.3
context_pages:
  - [[concepts/c-2026-04-shot-noise]]
analysis_pages:
  - [[findings/f-2026-05-shot-noise]]
---

# Description
(Prose context — what's in the data, gotchas, known issues.)
```

Manifests link bidirectionally with kb. Lint enforces both directions.

---

## 20. What's deferred

- Multi-user collaboration.
- Search beyond `index.md`.
- CI integration (lint in CI).
- Web search ingest.
- Cross-spec contradiction review.

---

For the focused reference documents on individual topics (frontmatter, link conventions, lint rules, exchange protocol, promotion protocol, role template, capabilities), see the files in `_framework/schema/`.
