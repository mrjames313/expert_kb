# Role Template

A role file lives at `<area>/roles/<role-name>/role.md` and defines what context an agent in that role loads and what they're allowed to do.

The template below shows the full shape. Sections marked `# capability: X` are inserted by the `/framework` skill when the relevant capability is enabled and removed when it's disabled. Don't add these sections manually.

## Two-tier preload

A role's preload list has two tiers:

- **Full preload** — small, curated; bodies are loaded. Schema docs, brief, POR, pulse, and a handful of frequently-referenced kb pages.
- **Frontmatter preload** — broad; only frontmatter blocks loaded. Specified as directory patterns. Cheap to scan, useful for "what's available in my area" awareness without bloating context.

The agent's session-start context is "full preload bodies + frontmatter blocks from files matching the frontmatter preload patterns." Bodies of other pages get loaded on demand when material to the work at hand.

## Template

```markdown
---
role: <role-name>
area: <area-path>
summary: <one sentence describing what this role does>
---

# <Role Name>

## Preload context (full)

Schema and conventions:
1. /CLAUDE.md
2. /_framework/schema/frontmatter.md
3. /_framework/schema/link-conventions.md

Project and parent area:
4. /commons/brief.md
5. /commons/pulse.md
# capability: por
6. /commons/POR.md
# end capability: por
7. /areas/<parent>/brief.md                 # only for sub-areas
8. /areas/<parent>/pulse.md                 # only for sub-areas
# capability: por
9. /areas/<parent>/POR.md                   # only for sub-areas
# end capability: por

Own area:
10. /areas/<area-path>/brief.md
11. /areas/<area-path>/pulse.md
# capability: por
12. /areas/<area-path>/POR.md
# end capability: por
13. /areas/<area-path>/kb/index.md

## Preload context (frontmatter only)

Patterns — load frontmatter blocks of all pages under these paths:

- /commons/kb/findings/
- /commons/kb/decisions/
- /areas/<area-path>/kb/

Optional individual additions (for parent-area context if sub-area):
- /areas/<parent>/kb/findings/

## Operating boundaries

- Writes allowed: /areas/<area-path>/** EXCEPT /areas/<area-path>/raw/**.
- Raw materials anywhere are read-only; existing files immutable. New raw materials are added through `/ingest`.
- Writes to /commons/: not directly. New content via /propose-promotion; corrections to an existing commons page via /amend-commons (light gate).
- Writes to other areas: avoid — use /exchange. The `commons_twin` back-pointer is the one sanctioned exception.
# capability: multi_area
- Cross-area knowledge: occasional reads are fine; prefer /exchange over repeated deep reads into other areas' kb.
# end capability: multi_area
- Reads allowed: full repo.

## Allowed skills

All always-available skills — see `_framework/schema/capabilities.md` → "Always-available skills" (the single source of truth; don't re-enumerate them here, or the list goes stale). The capability-gated skills below are added/removed by `/framework` and refreshed by `/framework resync`:
# capability: multi_area
exchange, respond-exchange, close-exchange, answer-from-kb
# end capability: multi_area
# capability: formal_review
review
# end capability: formal_review

## Default behaviors

- Cite using [[wikilinks]].
- When citing a concept, surface its status ("we're testing whether...", "we have evidence that...").
- When ending a session, run /wrap-up before clearing.
- When a task's plan looks wrong, invoke /replan; do not improvise.
- Ask the human in conversation when uncertain. INBOX is for items the human will see later, not a substitute for asking now.
- When you create or substantively update a notable page, evaluate whether it should be in a role's preload — file an INBOX "Heads up" suggestion if yes.
```

## Reviewer role variants

When `formal_review` is enabled, a reviewer variant exists for each implementer role:

- **Preload context** — same as the implementer role (both tiers).
- **Operating boundaries** — read full repo; writes restricted to the verdict file at `commons/_proposed/<slug>/verdict-<area>.md` (or equivalent for task review).
- **Allowed skills** — only `review`.

## Coordinator role

When `por` is enabled, a project-wide coordinator role lives at `commons/roles/coordinator/role.md`. It is read-broad, write-narrow:

- **Full preload** — `CLAUDE.md`, schema files, `commons/brief.md`, `commons/POR.md`, `commons/pulse.md`, `areas-index.md`, `INBOX.md`, all area `POR.md` files, all area `pulse.md` files.
- **Frontmatter preload** — all area `kb/` directories.
- **Operating boundaries** — writes allowed to `INBOX.md`, `commons/POR.md`, and to specs across areas. Cannot write area kb or commons kb.
- **Purpose** — cross-area planning, INBOX management, POR updates, routing for requests that span multiple areas.

## Frontmatter preload mechanics

The `start` skill, when loading a role, processes the frontmatter preload patterns as follows:

1. For each pattern, recursively find all `.md` files in matching directories.
2. For each file, extract only the frontmatter block (content between the leading and closing `---`).
3. Append each block to the agent's context with the file path as a reference.

This gives the agent visibility into many pages without loading their bodies. When the agent decides a page is material, it follows the wikilink to load the body.
