# Setup: Expert Coordination

This is a setup script for [Expert Coordination](https://github.com/mrjames313/expert_kb).

**For humans:** to use this script, launch Claude Code in a fresh directory and tell it:

> Follow the setup instructions at https://github.com/mrjames313/expert_kb/blob/main/SETUP.md

Claude will read this document and bootstrap a new project, asking you the necessary questions along the way. Setup takes 5–10 minutes.

---

## For the agent following this guide

You are helping a human user bootstrap a new project. Follow the steps below in order. Ask each question conversationally, one at a time. Show file contents back to the user for confirmation before writing. Don't batch questions.

The framework's full specification will be available at `_framework/spec.md` once the template is cloned in Step 2 — read it then if you need background.

---

### Step 1: Project name

Ask the user:

> What would you like to name your project? Use lowercase letters, numbers, and hyphens — no spaces. (This will be the directory name.)

Record the response as `$PROJECT_NAME`.

Check whether `./$PROJECT_NAME/` already exists. If it does, ask:

> A directory called `$PROJECT_NAME` already exists. Would you like to choose a different name, or cancel setup?

Don't overwrite without explicit confirmation.

---

### Step 2: Clone the template

Run:

```bash
git clone https://github.com/mrjames313/expert_kb.git $PROJECT_NAME
cd $PROJECT_NAME
rm -rf .git
git init -b main
git add .
git commit -m "Initial setup from framework template"
```

If the clone fails (network, permissions, etc.), tell the user, suggest they check network and git access, and stop.

From this point on, you have the full framework template available locally. Read `_framework/spec.md` if you need context, and use `_framework/schema/role-template.md` as the template for the role file you'll create in Step 5.

---

### Step 3: Project brief

Ask the user:

> In a few sentences, tell me about this project. What's it trying to achieve? Who is it for? What does success look like?

Take the response and write it to `commons/brief.md` using this shape:

```markdown
# Project Brief

[User's response, lightly formatted into 1–2 paragraphs. Preserve their wording; don't editorialize or add content they didn't say.]
```

Show the file to the user and ask:

> Here's the project brief. Looks right, or anything to change?

Iterate until they approve.

---

### Step 4: First area

Ask the user:

> What's the first area of work you want to set up? Common choices: research, engineering, product, business-model. Pick one to start — you can add more later.

Record as `$AREA_NAME`. Create the area structure:

```bash
mkdir -p areas/$AREA_NAME/{kb/findings,kb/decisions,kb/concepts,kb/sources,raw,data/manifests,specs,roles,_journal}
```

Ask the user:

> In a few sentences, what does the `$AREA_NAME` area focus on? What questions does it own? What's outside its scope?

Write the response to `areas/$AREA_NAME/brief.md`. Show it back for confirmation.

Initialize `areas/$AREA_NAME/pulse.md` with:

```markdown
# $AREA_NAME — pulse

_Initialized: [today's date in YYYY-MM-DD]_

## Current focus
_(set when work begins)_

## Recent decisions (last 7 active days)
_None yet._

## Active concepts under test
_None yet._

## Open questions
_None yet._

## Recent findings (last 5)
_None yet._
```

Create empty `areas/$AREA_NAME/_journal/pulse.log` and `areas/$AREA_NAME/kb/index.md`.

---

### Step 5: First role

Ask the user:

> What kind of agent will do most of the work in this area? Examples: "researcher" for research, "hardware-engineer" for engineering, "product-manager" for product. What would you like to call this role?

Record as `$ROLE_NAME`. Then ask:

> In one sentence, describe what this role does. (For example: "Investigates research questions, designs experiments, and maintains the area's knowledge base.")

Read `_framework/schema/role-template.md` and fill in:

- `role: $ROLE_NAME`
- `area: $AREA_NAME`
- `summary: [user's one-sentence description]`
- **Preload list**: `/CLAUDE.md`, `/_framework/schema/frontmatter.md`, `/_framework/schema/link-conventions.md`, `/commons/brief.md`, `/commons/pulse.md`, `/areas/$AREA_NAME/brief.md`, `/areas/$AREA_NAME/pulse.md`, `/areas/$AREA_NAME/kb/index.md`.
- **Operating boundaries**: writes allowed in `/areas/$AREA_NAME/**` except `/areas/$AREA_NAME/raw/**`; raw materials read-only; writes to `/commons/` forbidden (use `/propose-promotion`); reads allowed anywhere.
- **Allowed skills**: use the **referencing** form from `role-template.md` — *"All always-available skills — see `_framework/schema/capabilities.md` → 'Always-available skills'."* Do **not** enumerate the baseline list here or in the role file: copying it is the drift bug that silently withholds newly-shipped skills from a role (see `capabilities.md`). Since `multi_area` is off by default, add no capability-gated skill blocks yet; the user can enable them later via `/framework enable multi_area` when they have a second area.
- **Default behaviors**: cite via wikilinks; when citing a concept, surface its status; run `/wrap-up` before clearing context; ask in conversation when uncertain.

Write the filled-in file to `areas/$AREA_NAME/roles/$ROLE_NAME/role.md`. Show it back for confirmation.

---

### Step 6: Clean up, verify, and commit

**Clean up template artifacts.** The clone brought in files that only exist to bootstrap and have no place in a live project. Do this before committing — you already hold the rest of this runbook in context, so removing `SETUP.md` won't interrupt you.

Replace the framework's README with a short project-specific one drawn from the brief:

```markdown
# $PROJECT_NAME

[1–2 sentence summary of the project, drawn from `commons/brief.md`.]

Built on the Expert Coordination framework. See `CLAUDE.md` for how this project operates, and `_framework/adoption-guide.md` to extend it.
```

Show it to the user for confirmation, then remove the bootstrap runbook and the framework-authoring docs — none of these belong in a live project:

```bash
rm SETUP.md UPGRADING.md _framework/future-work.md _framework/maintaining.md _framework/clause-audit.md
```

Ask the user about the license:

> The template ships under the MIT license (`LICENSE`), which covers the framework itself. Keep it, replace it with your own project's license, or remove it?

Follow their choice.

Install the lint tool's dependencies (one-time per project):

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r _framework/tools/requirements.txt
```

If the user already has a venv or prefers system Python, ask which they'd like and follow their preference. (For system-wide install on systems that require it, use `pip install --break-system-packages -r _framework/tools/requirements.txt` instead.)

Run the linter:

```bash
python _framework/tools/lint.py
```

Surface any errors to the user. If the linter is clean, commit:

```bash
git add .
git commit -m "Customize project: brief, area $AREA_NAME, role $ROLE_NAME"
```

---

### Step 7: Tell the user it's done

Tell the user:

> Setup complete. Your project is at `./$PROJECT_NAME/`. To start working:
>
> 1. `cd $PROJECT_NAME`
> 2. Launch Claude Code from this directory.
> 3. Type a request like "look into [topic]" or "ingest this paper" — the agent will load your `$ROLE_NAME` role and get to work.
>
> When you're ready to add capabilities or areas, the adoption guide at `_framework/adoption-guide.md` walks through what's available. The full framework spec is at `_framework/spec.md`.

---

## Notes for the agent

- Ask questions one at a time. Don't batch.
- Show file contents back for approval before writing. Iterate if the user wants changes.
- If the user wants to skip a step, accept but warn that the project won't be fully functional without it (e.g., no role means no working agent on first launch).
- Don't add extra areas, roles, or enable capabilities beyond what's asked. Extensions happen later through `/framework enable` or by adding to the existing structure.
- If something fails (clone error, lint error), stop and surface the issue rather than continuing in a broken state.
- The user is in conversation with you throughout — keep tone natural, not script-like. The steps below are your runbook, not lines to read aloud.
