# Capabilities

The framework has four togglable capabilities. The `/framework` skill reads this document and applies the listed changes when capabilities are enabled or disabled.

Each capability section below describes:

- **Identity** — the key in `config.yml`.
- **Default** — initial state at template bootstrap.
- **Dependencies** — capabilities that must also be enabled.
- **Files created on enable** — what comes into existence.
- **Files made inert on disable** — content that stays on disk but stops being referenced.
- **CLAUDE.md sections** — which schema document sections are added/removed; references the snippet files in `claude-snippets/` that contain the actual text.
- **Role file edits** — what changes in role files (preload lists, boundaries, allowed skills).
- **Skill availability** — which skills become available or unavailable.
- **Lint rule changes** — which rules start or stop running.

## Skill activation

All skills ship with the template in `.claude/skills/` (don't hardcode a count here — it drifts as skills are added). Capability gating controls **activation state**, not file presence:

- The `framework` skill maintains a registry of currently-active skills.
- Capability-gated skills are present on disk but not active until their capability is enabled.
- `/framework enable <capability>` activates the gated skills; `/framework disable <capability>` deactivates them.
- Activation mechanism is implementation-defined (could be a registration manifest, file rename, or symlink scheme); the skill's SKILL.md content is preserved either way.

Re-enabling a capability picks up the existing skill files where they are — no regeneration.

## Always-available skills

This is the **single source of truth** for the baseline skill set — the skills every role may use regardless of which capabilities are enabled. Role files **reference** this list rather than enumerating it, so shipping a new always-available skill reaches every existing role on the next `/framework resync` (or upgrade) without editing any role file. (The old design copied the enumeration into each role file, which silently withheld newly-shipped skills like `amend-commons` from existing roles.)

```
start, ingest, ask, plan, implement, replan, wrap-up, check,
propose-promotion, promote, amend-commons, framework, budget, add-area, kb-vitals
```

When you ship a new always-available skill, add it here and nowhere else. Capability-gated skills are **not** in this list — they activate with their capability (see each capability's "Role file edits" below and spec.md §15):

- `multi_area` → `exchange, respond-exchange, close-exchange, answer-from-kb` (added to role Allowed skills).
- `formal_review` → `review` (added to implementer roles' Allowed skills) and `review-promotion` (activated with the capability; invoked in the promotion flow rather than listed per implementer role).

Two role kinds hold a **deliberate restriction** of the baseline rather than referencing it in full, and so keep an explicit list: the **coordinator** (a curated read-broad/write-narrow subset) and **reviewer** variants (limited to `review`). Those explicit lists are intentional curations, not the drift this section prevents.

## CLAUDE.md snippets

Each capability has an associated snippet file in `_framework/schema/claude-snippets/<capability>.md` containing the exact CLAUDE.md section text to insert on enable. The `framework` skill reads the snippet file and splices it into CLAUDE.md at a marker position (between always-on sections, before "Escalation triggers").

On disable, the framework skill identifies the snippet's boundaries in CLAUDE.md (via the section heading) and removes it.

---

## `multi_area`

**Identity**: `capabilities.multi_area`

**Default**: `false`

**Dependencies**: none

**Files created on enable**: none (exchange directories are created on demand by `/exchange` when first invoked).

**Files made inert on disable**: existing `exchanges/<a>--<b>/` directories. They remain on disk but skills become unavailable.

**CLAUDE.md sections**:
- Insert on enable: contents of `_framework/schema/claude-snippets/multi_area.md`.
- Remove on disable: same.

**Role file edits**:
- Insert in **Operating boundaries** (on enable): "Cross-area knowledge: occasional reads are fine; prefer `/exchange` over repeated deep reads into other areas' kb."
- Insert in **Allowed skills** (on enable): `exchange, respond-exchange, close-exchange, answer-from-kb`.
- Remove on disable: same.

**Skill availability**: `exchange`, `respond-exchange`, `close-exchange`, `answer-from-kb`.

**Lint rule changes**: Rule 14 (exchange staleness) starts running on enable.

---

## `por`

**Identity**: `capabilities.por`

**Default**: `false`

**Dependencies**: none

**Files created on enable**:
- `commons/POR.md` (placeholder template; user fills in).
- `areas/<area>/POR.md` for every existing area and sub-area (same).
- `commons/roles/coordinator/role.md` with the coordinator role definition.

**Files made inert on disable**: existing POR files remain on disk. The coordinator role file is removed from `commons/roles/`.

**CLAUDE.md sections**:
- Insert on enable: contents of `_framework/schema/claude-snippets/por.md`.
- Remove on disable: same.

**Role file edits**:
- Insert in **Full preload** (on enable, every role): `/commons/POR.md` and `/areas/<their-area>/POR.md`.
- Remove on disable: same.

**Skill availability**: none added. The `wrap-up` skill changes behavior (prompts for POR updates when relevant events happened), but the skill itself is always available.

**Lint rule changes**: none.

**Coordinator role behavior**: the coordinator handles cross-area routing for requests that span multiple areas. When `por` is disabled, the `start` skill asks the human to pick an area instead of auto-routing to a coordinator.

---

## `task_subagents`

**Identity**: `capabilities.task_subagents`

**Default**: `false`

**Dependencies**: none

**Files created on enable**: none.

**Files made inert on disable**: none.

**CLAUDE.md sections**:
- Insert on enable: contents of `_framework/schema/claude-snippets/task_subagents.md`.
- Remove on disable: same.

**Role file edits**: none.

**Skill availability**: none added. The `/implement` skill changes behavior — without `task_subagents`, it runs the work in the current agent; with `task_subagents`, it spawns a fresh subagent loaded from the role's preload list.

**Lint rule changes**: none.

---

## `formal_review`

**Identity**: `capabilities.formal_review`

**Default**: `false`

**Dependencies**: `task_subagents` must be enabled. If `formal_review` is requested without `task_subagents`, the `framework` skill offers to enable both.

**Files created on enable**: for each existing area, a reviewer variant of each role at `areas/<area>/roles/<role-name>-reviewer/role.md`. Reviewer role files are derived from the implementer role's preload list (both tiers), with `Operating boundaries` restricted to writes within the verdict file path, and `Allowed skills` limited to `review`.

**Files made inert on disable**: reviewer role files are removed from each area's `roles/` directory.

**CLAUDE.md sections**:
- Insert on enable: contents of `_framework/schema/claude-snippets/formal_review.md`.
- Remove on disable: same.

**Role file edits**:
- Insert in **Allowed skills** (on enable, implementer roles only): `review`.
- Remove on disable: same.

**Skill availability**: `review`, `review-promotion`.

**Lint rule changes**: none.

**Behavior changes**:
- `/implement` followed by `/review` now spawns a reviewer subagent that produces a verdict.
- Two rejections trigger an auto-debug subagent.
- `/propose-promotion` triggers `/review-promotion` for each other area; per-area verdict subagents produce `verdict-<area>.md` files. Consensus rules apply.

---

## Lint warning toggles

Separately from capabilities, individual lint warning rules can be enabled or disabled via `/framework enable-lint <rule>` and `/framework disable-lint <rule>`. The configurable rules are listed in `lint-rules.md`. Default: all warning rules are shadowed (off-visible); errors are always visible.
