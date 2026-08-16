"""
Capability enable/disable engine and lint visibility commands.

Drives all the file edits documented in `_framework/schema/capabilities.md`:
- CLAUDE.md gets capability sections spliced in/out from snippet files.
- Role files gain/lose preload entries and skill entries per capability.
- Capability-specific files get created (POR.md, coordinator role, reviewer roles)
  or removed.
- config.yml reflects the new state.

Each capability change is computed as a `Plan` first (a list of `Change` records),
then applied. This separation supports `--dry-run` and makes the tool testable.

Public API:
    plan_enable(capability, repo_root, config) -> Plan
    plan_disable(capability, repo_root, config) -> Plan
    apply_plan(plan, repo_root) -> None
    enable_lint(rule, repo_root, config) -> Plan
    disable_lint(rule, repo_root, config) -> Plan
    status(repo_root, config) -> dict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from common import (  # noqa: E402
    find_repo_root,
    iter_areas,
    iter_role_files,
    load_config,
    parse_frontmatter,
)
from telemetry import iter_events  # noqa: E402
from token_estimate import parse_role_preload  # noqa: E402


# All capabilities the framework recognizes
KNOWN_CAPABILITIES = {"multi_area", "por", "task_subagents", "formal_review"}

def _discover_configurable_lint_rules() -> set[str]:
    """Derive the set of configurable (self-gating warning) lint rules from the
    shipped modules under `lint_rules/`, so this enabler can never drift from the
    rules that actually ship.

    A rule is configurable iff its module declares `SEVERITY == "warning"` and
    exposes a `CONFIG_KEY` — the `lint.warnings_visible` key it self-gates on.
    (Hardcoding this set is what let rules 20/21 ship while `enable-lint` still
    rejected them; see `_framework/schema/lint-rules.md`.)
    """
    import importlib

    rules_dir = Path(__file__).parent / "lint_rules"
    keys: set[str] = set()
    if not rules_dir.is_dir():
        return keys
    for path in sorted(rules_dir.glob("rule_*.py")):
        try:
            module = importlib.import_module(f"lint_rules.{path.stem}")
        except Exception:  # noqa: BLE001 — a broken rule must not break the enabler
            continue
        if getattr(module, "SEVERITY", None) == "warning" and getattr(module, "CONFIG_KEY", None):
            keys.add(module.CONFIG_KEY)
    return keys


# Configurable lint warning rules — derived from the shipped rule modules, not
# hardcoded (a hardcoded list drifted from what shipped and broke enable-lint).
CONFIGURABLE_LINT_RULES = _discover_configurable_lint_rules()

# Dependencies between capabilities
CAPABILITY_DEPENDENCIES = {
    "formal_review": {"task_subagents"},
}


# --- Plan / Change types ---

@dataclass
class Change:
    """One file modification."""
    kind: str  # "create" | "edit" | "delete"
    path: str  # relative to repo root
    description: str  # human-readable
    new_content: str | None = None  # for "create" or "edit"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "description": self.description,
        }


@dataclass
class Plan:
    """A set of changes to apply for one operation."""
    operation: str  # e.g. "enable multi_area"
    changes: list[Change] = field(default_factory=list)
    config_updates: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "changes": [c.to_dict() for c in self.changes],
            "config_updates": self.config_updates,
            "warnings": self.warnings,
            "error": self.error,
        }


class FrameworkError(RuntimeError):
    """Raised on irrecoverable errors during enable/disable."""


# --- Snippet handling ---

def _load_snippet(repo_root: Path, capability: str) -> str:
    """Load the CLAUDE.md snippet for a capability. Strip leading/trailing whitespace."""
    path = repo_root / "_framework" / "schema" / "claude-snippets" / f"{capability}.md"
    if not path.is_file():
        raise FrameworkError(f"snippet file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _wrap_claude_section(capability: str, snippet_text: str) -> str:
    """Wrap a snippet with begin/end markers and ensure a trailing blank line."""
    return f"<!-- begin capability: {capability} -->\n{snippet_text}\n<!-- end capability: {capability} -->\n"


# --- CLAUDE.md splicing ---

def insert_capability_section(claude_md: str, capability: str, snippet_text: str) -> str:
    """
    Insert a wrapped capability section into CLAUDE.md.

    If the capability already has a section (begin/end markers present),
    replaces it. Otherwise, inserts just before the "## Escalation triggers"
    section (or at the end if that section isn't found).
    """
    wrapped = _wrap_claude_section(capability, snippet_text)
    pattern = re.compile(
        rf"<!-- begin capability: {re.escape(capability)} -->.*?<!-- end capability: {re.escape(capability)} -->\n?",
        re.DOTALL,
    )

    if pattern.search(claude_md):
        # Replace existing block
        return pattern.sub(wrapped, claude_md)

    # Insert before "## Escalation triggers"
    insertion_marker = "## Escalation triggers"
    idx = claude_md.find(insertion_marker)
    if idx == -1:
        # No escalation triggers section; append at end (after a blank line)
        return claude_md.rstrip() + "\n\n" + wrapped + "\n"
    return claude_md[:idx] + wrapped + "\n" + claude_md[idx:]


def remove_capability_section(claude_md: str, capability: str) -> str:
    """Remove a capability's section from CLAUDE.md. No-op if absent."""
    pattern = re.compile(
        rf"<!-- begin capability: {re.escape(capability)} -->.*?<!-- end capability: {re.escape(capability)} -->\n?\n?",
        re.DOTALL,
    )
    return pattern.sub("", claude_md)


# --- Role file editing ---

def _role_capability_marker_begin(capability: str) -> str:
    return f"# capability: {capability}"


def _role_capability_marker_end(capability: str) -> str:
    return f"# end capability: {capability}"


def _insert_role_block(
    role_text: str,
    section_heading: str,
    capability: str,
    block_lines: list[str],
    *,
    position: str = "end",  # "end" of section, or "after_line:<text>"
) -> str:
    """
    Insert a capability block (with markers) into a section of a role file.
    If a block for this capability already exists in this section, do nothing.

    The block is inserted at the end of the section (just before the next ##)
    or after a specified line.
    """
    begin_marker = _role_capability_marker_begin(capability)
    end_marker = _role_capability_marker_end(capability)

    lines = role_text.splitlines()

    # Locate the section
    section_start = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## " + section_heading.lower()):
            section_start = i
            break
        # Also match parenthetical variants like "## Allowed skills (any version)"
        m = re.match(r"^## (.+?)(?:\s*\(.*\))?\s*$", line.strip())
        if m and m.group(1).strip().lower() == section_heading.lower():
            section_start = i
            break

    if section_start is None:
        return role_text  # section not found; leave unchanged

    # Locate the next section heading (or end of file)
    section_end = len(lines)
    for i in range(section_start + 1, len(lines)):
        if lines[i].startswith("## "):
            section_end = i
            break

    # If the marker block already exists in this section, skip
    section_text = "\n".join(lines[section_start:section_end])
    if begin_marker in section_text:
        return role_text

    # Determine insertion index
    insert_at = section_end
    if position.startswith("after_line:"):
        target = position[len("after_line:"):]
        for i in range(section_start + 1, section_end):
            if target.strip() in lines[i].strip():
                insert_at = i + 1
                break

    # Build the new block (with one blank line before, marker, content, marker, blank line after)
    new_lines = [
        "",
        begin_marker,
        *block_lines,
        end_marker,
    ]

    # Walk back from insert_at to skip trailing blank lines (so the block sits
    # cleanly against existing content)
    while insert_at > section_start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    result_lines = lines[:insert_at] + new_lines + lines[insert_at:]
    return "\n".join(result_lines)


def _remove_role_block(role_text: str, capability: str) -> str:
    """Remove all capability-marked blocks for the given capability from a role file."""
    begin_marker = _role_capability_marker_begin(capability)
    end_marker = _role_capability_marker_end(capability)

    # Fast path: no markers anywhere -> exact passthrough (preserves trailing newlines)
    if begin_marker not in role_text:
        return role_text

    lines = role_text.splitlines()
    result: list[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped == begin_marker:
            skip = True
            # Also strip preceding blank line if any (to avoid orphan blanks)
            while result and result[-1].strip() == "":
                result.pop()
            continue
        if stripped == end_marker:
            skip = False
            continue
        if not skip:
            result.append(line)

    new_text = "\n".join(result)
    # Preserve trailing newline if input had one
    if role_text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text


def _role_has_section(role_text: str, heading: str) -> bool:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}", re.MULTILINE | re.IGNORECASE)
    return bool(pattern.search(role_text))


# --- Per-capability enable/disable planners ---

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _role_metadata(role_path: Path) -> dict:
    try:
        fm, _ = parse_frontmatter(role_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return fm or {}


def _plan_claude_md(plan: Plan, repo_root: Path, capability: str, action: str) -> None:
    """Add the CLAUDE.md edit to a plan."""
    claude_md_path = repo_root / "CLAUDE.md"
    if not claude_md_path.is_file():
        plan.warnings.append("CLAUDE.md not found; skipping schema document edit")
        return

    current = _read_text(claude_md_path)
    if action == "enable":
        snippet = _load_snippet(repo_root, capability)
        new_content = insert_capability_section(current, capability, snippet)
    else:
        new_content = remove_capability_section(current, capability)

    if new_content != current:
        plan.changes.append(
            Change(
                kind="edit",
                path="CLAUDE.md",
                description=f"{action.capitalize()} capability section for {capability}",
                new_content=new_content,
            )
        )


# --- multi_area ---

def _plan_multi_area(plan: Plan, repo_root: Path, action: str) -> None:
    _plan_claude_md(plan, repo_root, "multi_area", action)

    boundary_line = (
        "- Cross-area knowledge: occasional reads are fine; prefer /exchange over "
        "repeated deep reads into other areas' kb."
    )
    skills_line = "exchange, respond-exchange, close-exchange, answer-from-kb"

    for role_path in iter_role_files(repo_root):
        rel = str(role_path.relative_to(repo_root))
        text = _read_text(role_path)

        if action == "enable":
            new_text = _insert_role_block(
                text,
                "Operating boundaries",
                "multi_area",
                [boundary_line],
            )
            new_text = _insert_role_block(
                new_text,
                "Allowed skills",
                "multi_area",
                [skills_line],
            )
        else:
            new_text = _remove_role_block(text, "multi_area")

        if new_text != text:
            plan.changes.append(
                Change(
                    kind="edit",
                    path=rel,
                    description=f"{action.capitalize()} multi_area entries",
                    new_content=new_text,
                )
            )


# --- por ---

def _plan_por(plan: Plan, repo_root: Path, action: str) -> None:
    _plan_claude_md(plan, repo_root, "por", action)

    if action == "enable":
        # Create POR.md files
        por_template = (
            "---\n"
            "type: por\n"
            "area: {area_value}\n"
            "phase: (set by coordinator or area roles)\n"
            "last_updated: (set on next update)\n"
            "---\n\n"
            "# Plan of Record — {area_label}\n\n"
            "## Current phase\n\n"
            "_(populate)_\n\n"
            "## Active workstreams\n\n"
            "_(populate)_\n\n"
            "## Upcoming\n\n"
            "_(populate)_\n\n"
            "## Dependencies\n\n"
            "_(populate)_\n\n"
            "## Status and risks\n\n"
            "_(populate)_\n"
        )

        commons_por_path = repo_root / "commons" / "POR.md"
        if not commons_por_path.is_file():
            plan.changes.append(
                Change(
                    kind="create",
                    path="commons/POR.md",
                    description="Create commons POR template",
                    new_content=por_template.format(area_value="commons", area_label="Commons"),
                )
            )

        for area_dir in iter_areas(repo_root):
            por_path = area_dir / "POR.md"
            if por_path.is_file():
                continue
            rel_area = str(area_dir.relative_to(repo_root))
            area_value = rel_area.replace("areas/", "", 1)
            plan.changes.append(
                Change(
                    kind="create",
                    path=str(por_path.relative_to(repo_root)),
                    description=f"Create {area_value} POR template",
                    new_content=por_template.format(area_value=area_value, area_label=area_value),
                )
            )

        # Create coordinator role
        coord_path = repo_root / "commons" / "roles" / "coordinator" / "role.md"
        if not coord_path.is_file():
            plan.changes.append(
                Change(
                    kind="create",
                    path=str(coord_path.relative_to(repo_root)),
                    description="Create commons coordinator role",
                    new_content=_coordinator_role_text(),
                )
            )

    else:  # disable
        # Remove coordinator role (POR files stay on disk)
        coord_path = repo_root / "commons" / "roles" / "coordinator" / "role.md"
        if coord_path.is_file():
            plan.changes.append(
                Change(
                    kind="delete",
                    path=str(coord_path.relative_to(repo_root)),
                    description="Remove commons coordinator role (file inert; deleted)",
                )
            )
        # POR files remain on disk; warn if any exist
        existing_pors = [
            p for p in [repo_root / "commons" / "POR.md", *[a / "POR.md" for a in iter_areas(repo_root)]]
            if p.is_file()
        ]
        if existing_pors:
            plan.warnings.append(
                f"{len(existing_pors)} POR.md file(s) remain on disk. They are now inert "
                f"(not referenced by role preloads or skills); re-enabling por picks them up."
            )

    # Role file edits — add/remove POR preload entries
    for role_path in iter_role_files(repo_root):
        # Skip the coordinator role (it has its own structure, not the standard preload sections)
        if "coordinator" in str(role_path):
            continue

        rel = str(role_path.relative_to(repo_root))
        text = _read_text(role_path)
        metadata = _role_metadata(role_path)
        area_value = str(metadata.get("area", "")).strip()

        if action == "enable":
            preload_lines = ["/commons/POR.md"]
            if area_value and area_value != "commons":
                # Add own-area POR. For sub-areas (a/b), also add parent POR.
                parts = area_value.split("/")
                # Walk from the most-specific area back through parents
                paths_to_add = []
                for i in range(len(parts), 0, -1):
                    sub_area = "/".join(parts[:i])
                    paths_to_add.append(f"/areas/{sub_area}/POR.md")
                preload_lines.extend(paths_to_add)
            block_lines = [f"- {p}" for p in preload_lines]
            new_text = _insert_role_block(
                text,
                "Preload context (full)",
                "por",
                block_lines,
            )
        else:
            new_text = _remove_role_block(text, "por")

        if new_text != text:
            plan.changes.append(
                Change(
                    kind="edit",
                    path=rel,
                    description=f"{action.capitalize()} por preload entries",
                    new_content=new_text,
                )
            )


def _coordinator_role_text() -> str:
    return (
        "---\n"
        "role: coordinator\n"
        "area: commons\n"
        "summary: Cross-area planning, INBOX management, POR updates, and "
        "routing for requests that span multiple areas.\n"
        "---\n\n"
        "# Coordinator\n\n"
        "Read-broad, write-narrow role for cross-area planning. Loads broad "
        "context across the project; writes only to INBOX, commons/POR.md, "
        "and specs across areas.\n\n"
        "## Preload context (full)\n\n"
        "Schema and conventions:\n"
        "1. /CLAUDE.md\n"
        "2. /_framework/schema/frontmatter.md\n"
        "3. /_framework/schema/link-conventions.md\n\n"
        "Project-wide state:\n"
        "4. /commons/brief.md\n"
        "5. /commons/POR.md\n"
        "6. /commons/pulse.md\n"
        "7. /areas-index.md\n"
        "8. /INBOX.md\n\n"
        "## Preload context (frontmatter only)\n\n"
        "Patterns:\n"
        "- /commons/kb/findings/\n"
        "- /commons/kb/decisions/\n"
        "- /areas/\n\n"
        "## Operating boundaries\n\n"
        "- Writes allowed: /INBOX.md, /commons/POR.md, /areas/**/specs/**.\n"
        "- Cannot write to area kb or commons kb directly.\n"
        "- Reads allowed: full repo.\n\n"
        "## Allowed skills\n\n"
        "start, ask, plan, replan, wrap-up, check, framework, budget, add-area\n\n"
        "## Default behaviors\n\n"
        "- Cite using [[wikilinks]].\n"
        "- For requests within a single area, route the work to that area's "
        "implementer role; do not implement directly.\n"
        "- Update POR when phases shift, workstreams change, or replans happen.\n"
        "- Ask the human in conversation when uncertain.\n"
    )


# --- task_subagents ---

def _plan_task_subagents(plan: Plan, repo_root: Path, action: str) -> None:
    _plan_claude_md(plan, repo_root, "task_subagents", action)
    # No role file or content edits; behavior change is in /implement skill itself.


# --- formal_review ---

def _plan_formal_review(plan: Plan, repo_root: Path, action: str) -> None:
    _plan_claude_md(plan, repo_root, "formal_review", action)

    if action == "enable":
        # Create reviewer variants of each implementer role
        for role_path in iter_role_files(repo_root):
            # Skip reviewer roles and the coordinator
            name = role_path.parent.name
            if name.endswith("-reviewer") or name == "coordinator":
                continue
            reviewer_dir = role_path.parent.parent / f"{name}-reviewer"
            reviewer_path = reviewer_dir / "role.md"
            if reviewer_path.is_file():
                continue
            content = _reviewer_role_text(role_path, name)
            plan.changes.append(
                Change(
                    kind="create",
                    path=str(reviewer_path.relative_to(repo_root)),
                    description=f"Create reviewer variant of {name}",
                    new_content=content,
                )
            )
    else:  # disable
        # Remove all reviewer role files
        for role_path in iter_role_files(repo_root):
            name = role_path.parent.name
            if name.endswith("-reviewer"):
                plan.changes.append(
                    Change(
                        kind="delete",
                        path=str(role_path.relative_to(repo_root)),
                        description=f"Remove reviewer role {name}",
                    )
                )

    # Implementer role files get "review" added to allowed skills on enable;
    # removed on disable. Reviewer roles themselves are exempt (they only have `review`).
    for role_path in iter_role_files(repo_root):
        name = role_path.parent.name
        if name.endswith("-reviewer") or name == "coordinator":
            continue

        rel = str(role_path.relative_to(repo_root))
        text = _read_text(role_path)
        if action == "enable":
            new_text = _insert_role_block(
                text,
                "Allowed skills",
                "formal_review",
                ["review"],
            )
        else:
            new_text = _remove_role_block(text, "formal_review")

        if new_text != text:
            plan.changes.append(
                Change(
                    kind="edit",
                    path=rel,
                    description=f"{action.capitalize()} formal_review skill entry",
                    new_content=new_text,
                )
            )


def _reviewer_role_text(implementer_path: Path, role_name: str) -> str:
    """Derive a reviewer-role file from an implementer's role file."""
    text = implementer_path.read_text(encoding="utf-8")
    fm, _body = parse_frontmatter(text)
    if not fm:
        fm = {}
    area = fm.get("area", "unknown")
    summary = f"Independent reviewer for {role_name}; reads broadly, writes only verdict files."

    # Pull the preload sections verbatim from the implementer's role file
    sections = _extract_preload_sections(text)

    out = [
        "---",
        f"role: {role_name}-reviewer",
        f"area: {area}",
        f"summary: {summary}",
        "---",
        "",
        f"# {role_name}-reviewer",
        "",
        "Stripped-down reviewer variant of the implementer role. Same context, "
        "narrower write surface, single skill.",
        "",
    ]

    if sections["full"]:
        out.append("## Preload context (full)")
        out.append("")
        out.extend(sections["full"])
        out.append("")

    if sections["frontmatter"]:
        out.append("## Preload context (frontmatter only)")
        out.append("")
        out.extend(sections["frontmatter"])
        out.append("")

    out.extend([
        "## Operating boundaries",
        "",
        "- Writes allowed: only the verdict file for the task or proposal under review.",
        "- Reads allowed: full repo.",
        "- Cannot modify implementer outputs; only produce a verdict with rationale.",
        "",
        "## Allowed skills",
        "",
        "review",
        "",
        "## Default behaviors",
        "",
        "- Verdict values: APPROVE | OBJECT | ABSTAIN.",
        "- OBJECT requires concrete rationale in the verdict's Concerns section.",
        "- ABSTAIN means \"this doesn't materially affect our area's work.\"",
        "- Use the same citation conventions as implementer roles.",
        "",
    ])

    return "\n".join(out)


def _extract_preload_sections(text: str) -> dict[str, list[str]]:
    """Extract the body lines of "Preload context (full)" and "Preload context (frontmatter only)"."""
    out = {"full": [], "frontmatter": []}
    lines = text.splitlines()
    current = None
    for line in lines:
        m = re.match(r"^##\s+Preload context \((full|frontmatter only)\)\s*$", line, re.IGNORECASE)
        if m:
            current = "full" if m.group(1).lower() == "full" else "frontmatter"
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is not None:
            out[current].append(line)
    # Trim trailing blanks from each section
    for k in out:
        while out[k] and out[k][-1].strip() == "":
            out[k].pop()
    return out


# --- Plan composition ---

PLANNERS = {
    "multi_area": _plan_multi_area,
    "por": _plan_por,
    "task_subagents": _plan_task_subagents,
    "formal_review": _plan_formal_review,
}


def plan_enable(capability: str, repo_root: Path, config: dict) -> Plan:
    """Build a plan to enable a capability."""
    plan = Plan(operation=f"enable {capability}")

    if capability not in KNOWN_CAPABILITIES:
        plan.error = f"unknown capability: {capability!r}"
        return plan

    current = config.get("capabilities", {}).get(capability, False)
    if current:
        plan.warnings.append(f"{capability} is already enabled; no changes needed.")
        return plan

    # Check dependencies
    deps = CAPABILITY_DEPENDENCIES.get(capability, set())
    missing_deps = [d for d in deps if not config.get("capabilities", {}).get(d, False)]
    if missing_deps:
        plan.warnings.append(
            f"{capability} requires {', '.join(missing_deps)} to be enabled first. "
            f"Enable that first, or run `/framework enable {missing_deps[0]}` then retry."
        )
        plan.error = "unmet dependency"
        return plan

    PLANNERS[capability](plan, repo_root, "enable")
    plan.config_updates[f"capabilities.{capability}"] = True
    return plan


def plan_disable(capability: str, repo_root: Path, config: dict) -> Plan:
    """Build a plan to disable a capability."""
    plan = Plan(operation=f"disable {capability}")

    if capability not in KNOWN_CAPABILITIES:
        plan.error = f"unknown capability: {capability!r}"
        return plan

    current = config.get("capabilities", {}).get(capability, False)
    if not current:
        plan.warnings.append(f"{capability} is already disabled; no changes needed.")
        return plan

    # Check reverse dependencies — disabling a dependency requires disabling dependents first
    dependents = [
        cap for cap, deps in CAPABILITY_DEPENDENCIES.items()
        if capability in deps and config.get("capabilities", {}).get(cap, False)
    ]
    if dependents:
        plan.error = (
            f"cannot disable {capability}: {', '.join(dependents)} depends on it. "
            f"Disable those first."
        )
        return plan

    PLANNERS[capability](plan, repo_root, "disable")
    plan.config_updates[f"capabilities.{capability}"] = False
    return plan


# --- Plan application ---

def apply_plan(plan: Plan, repo_root: Path) -> None:
    """Apply all changes in a plan and update config. Raises FrameworkError on failure."""
    if plan.error:
        raise FrameworkError(f"plan has error, refusing to apply: {plan.error}")

    repo_root = repo_root.resolve()

    for change in plan.changes:
        target = repo_root / change.path
        if change.kind == "create":
            if target.exists():
                # Race condition or stale plan; surface this
                raise FrameworkError(f"refusing to create {change.path}: already exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.new_content or "", encoding="utf-8")
        elif change.kind == "edit":
            if not target.is_file():
                raise FrameworkError(f"refusing to edit {change.path}: not a file")
            target.write_text(change.new_content or "", encoding="utf-8")
        elif change.kind == "delete":
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                import shutil
                shutil.rmtree(target)
            # If the parent role dir is now empty, remove it too
            parent = target.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        else:
            raise FrameworkError(f"unknown change kind: {change.kind}")

    # Update config.yml
    if plan.config_updates:
        _update_config(repo_root, plan.config_updates)


def _update_config(repo_root: Path, updates: dict[str, object]) -> None:
    """Apply dotted-key updates to config.yml in place."""
    config_path = repo_root / "_framework" / "config.yml"
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    for key, value in updates.items():
        parts = key.split(".")
        cursor = config
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


# --- Lint visibility commands ---

def plan_enable_lint(rule: str, repo_root: Path, config: dict) -> Plan:
    """Build a plan to make a shadow lint rule visible."""
    plan = Plan(operation=f"enable-lint {rule}")
    rule_key = _normalize_lint_rule(rule)
    if rule_key not in CONFIGURABLE_LINT_RULES:
        plan.error = (
            f"unknown configurable lint rule: {rule!r}. "
            f"Known: {', '.join(sorted(CONFIGURABLE_LINT_RULES))}"
        )
        return plan
    current = config.get("lint", {}).get("warnings_visible", {}).get(rule_key, False)
    if current:
        plan.warnings.append(f"{rule_key} is already visible.")
        return plan
    plan.config_updates[f"lint.warnings_visible.{rule_key}"] = True
    return plan


def plan_disable_lint(rule: str, repo_root: Path, config: dict) -> Plan:
    """Build a plan to shadow a previously visible lint rule."""
    plan = Plan(operation=f"disable-lint {rule}")
    rule_key = _normalize_lint_rule(rule)
    if rule_key not in CONFIGURABLE_LINT_RULES:
        plan.error = f"unknown configurable lint rule: {rule!r}"
        return plan
    current = config.get("lint", {}).get("warnings_visible", {}).get(rule_key, False)
    if not current:
        plan.warnings.append(f"{rule_key} is already shadowed.")
        return plan
    plan.config_updates[f"lint.warnings_visible.{rule_key}"] = False
    return plan


def _normalize_lint_rule(rule: str) -> str:
    """Accept '04', 'rule_4', or 'rule_4_orphans' and return canonical key."""
    rule = rule.strip().lstrip("0")
    if rule.startswith("rule_"):
        # Try to match an existing key by prefix
        for known in CONFIGURABLE_LINT_RULES:
            if known.startswith(rule):
                return known
        return rule
    if rule.isdigit():
        # Find a rule_<n>_... key
        for known in CONFIGURABLE_LINT_RULES:
            if known.startswith(f"rule_{rule}_"):
                return known
    return rule


# --- Prune (stale preload entry detection) ---

# Statuses that make a kb page unfit to keep in a role's preload.
DEAD_STATUSES = {"superseded", "falsified", "dropped"}


@dataclass
class PruneCandidate:
    """One preload entry suggested for removal from a role file."""
    role_file: str  # relative to repo root
    role_name: str
    preload_path: str  # the path or pattern as it appears in the role file
    tier: str  # "full" or "frontmatter"
    reason: str  # human-readable explanation
    detail: dict = field(default_factory=dict)
    in_capability_block: bool = False  # capability-managed; will be skipped on apply

    def to_dict(self) -> dict:
        return {
            "role_file": self.role_file,
            "role_name": self.role_name,
            "preload_path": self.preload_path,
            "tier": self.tier,
            "reason": self.reason,
            "detail": self.detail,
            "in_capability_block": self.in_capability_block,
        }


def _gather_role_sessions(repo_root: Path, role_name: str, limit: int) -> list[dict]:
    """
    Return up to `limit` most-recent completed sessions for the given role.
    A completed session has both a session_start and a session_end event.
    """
    starts: dict[str, dict] = {}
    ends: dict[str, dict] = {}
    for event in iter_events(repo_root):
        sid = event.get("session_id")
        if not sid:
            continue
        if event.get("event") == "session_start" and event.get("role") == role_name:
            starts[sid] = event
        elif event.get("event") == "session_end":
            ends[sid] = event
    paired = []
    for sid, start in starts.items():
        end = ends.get(sid)
        if end is not None:
            paired.append({"start": start, "end": end})
    # Most recent first by session_id (which is timestamp-based)
    paired.sort(key=lambda p: p["start"].get("session_id", ""), reverse=True)
    return paired[:limit]


def _normalize_path(path: str) -> str:
    """Strip leading slash and trailing slash for canonical comparison."""
    return path.strip().lstrip("/").rstrip("/")


def _path_in_pattern(cited_path: str, pattern: str) -> bool:
    """Check if a cited path falls within a directory pattern."""
    cn = _normalize_path(cited_path)
    pn = _normalize_path(pattern)
    return cn == pn or cn.startswith(pn + "/")


def _parse_role_preload_with_capability_markers(role_text: str) -> dict:
    """
    Parse a role file's preload sections, also marking which entries are inside
    capability blocks (`# capability: X` … `# end capability: X`).

    Returns:
        {
          "full": [{"path": str, "in_capability_block": bool, "capability": str|None}, ...],
          "frontmatter": [{"path": str, "in_capability_block": bool, "capability": str|None}, ...],
        }
    """
    out = {"full": [], "frontmatter": []}
    current_section: str | None = None
    current_capability: str | None = None

    line_pat = re.compile(r"^\s*(?:\d+\.|-)\s+(.+?)\s*$")
    for raw in role_text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            heading = line.lstrip("#").strip().lower()
            if heading.startswith("preload context (full)"):
                current_section = "full"
            elif heading.startswith("preload context (frontmatter"):
                current_section = "frontmatter"
            else:
                current_section = None
            current_capability = None
            continue
        if current_section is None:
            continue

        stripped = line.strip()
        cap_match = re.match(r"^#\s+capability:\s+(\S+)\s*$", stripped)
        if cap_match:
            current_capability = cap_match.group(1)
            continue
        if stripped.startswith("# end capability:"):
            current_capability = None
            continue

        m = line_pat.match(line)
        if not m:
            continue
        content = m.group(1)
        # Strip trailing comment and backticks
        content = re.sub(r"\s+#.*$", "", content).strip().strip("`")
        if not content.startswith("/"):
            continue
        out[current_section].append({
            "path": content.lstrip("/"),
            "raw_line_path": content,  # preserves the leading slash for line matching
            "in_capability_block": current_capability is not None,
            "capability": current_capability,
        })

    return out


def find_prune_candidates(
    repo_root: Path,
    config: dict,
    *,
    role_filter: str | None = None,
) -> list[PruneCandidate]:
    """
    Identify preload entries that are stale or dead-weight across role files.

    Two sources of staleness:
      1. Lifecycle: target page exists and has status in {superseded, falsified, dropped}.
      2. Activity: target path was not cited across the last N sessions for the role
         (N from config.prune.{full_tier,frontmatter_tier}_stale_sessions).

    role_filter (if given) restricts to role files whose `role` frontmatter matches.
    """
    prune_cfg = config.get("prune", {}) if isinstance(config, dict) else {}
    full_threshold = int(prune_cfg.get("full_tier_stale_sessions", 10))
    frontmatter_threshold = int(prune_cfg.get("frontmatter_tier_stale_sessions", 30))

    candidates: list[PruneCandidate] = []

    for role_path in iter_role_files(repo_root):
        try:
            role_text = role_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            fm, _body = parse_frontmatter(role_text)
        except Exception:  # noqa: BLE001
            fm = None
        role_name = (fm or {}).get("role", role_path.parent.name)

        if role_filter and role_name != role_filter:
            continue

        rel_role = str(role_path.relative_to(repo_root))
        preload = _parse_role_preload_with_capability_markers(role_text)

        # --- Lifecycle-driven (full tier only — patterns don't have a status) ---
        for entry in preload["full"]:
            target = repo_root / entry["path"]
            if not target.is_file():
                continue  # missing files surface via token_estimate, not here
            try:
                target_fm, _ = parse_frontmatter(target.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if target_fm and target_fm.get("status") in DEAD_STATUSES:
                candidates.append(PruneCandidate(
                    role_file=rel_role,
                    role_name=role_name,
                    preload_path=entry["raw_line_path"],
                    tier="full",
                    reason=f"target page has status {target_fm['status']!r}",
                    detail={"page_status": target_fm["status"]},
                    in_capability_block=entry["in_capability_block"],
                ))

        # --- Activity-driven (require enough session history) ---
        sessions_full = _gather_role_sessions(repo_root, role_name, full_threshold)
        sessions_fm = _gather_role_sessions(repo_root, role_name, frontmatter_threshold)

        if len(sessions_full) >= full_threshold:
            cited_paths: set[str] = set()
            for s in sessions_full:
                end = s.get("end") or {}
                for p in end.get("pages_cited", []) or []:
                    cited_paths.add(_normalize_path(p))
            already_flagged = {c.preload_path for c in candidates if c.role_file == rel_role}
            for entry in preload["full"]:
                # Don't double-flag if already lifecycle-flagged
                if entry["raw_line_path"] in already_flagged:
                    continue
                normalized = _normalize_path(entry["path"])
                if normalized not in cited_paths:
                    candidates.append(PruneCandidate(
                        role_file=rel_role,
                        role_name=role_name,
                        preload_path=entry["raw_line_path"],
                        tier="full",
                        reason=f"not cited in last {full_threshold} sessions",
                        detail={"sessions_examined": len(sessions_full)},
                        in_capability_block=entry["in_capability_block"],
                    ))

        if len(sessions_fm) >= frontmatter_threshold:
            cited_paths_fm: set[str] = set()
            for s in sessions_fm:
                end = s.get("end") or {}
                for p in end.get("pages_cited", []) or []:
                    cited_paths_fm.add(_normalize_path(p))
            for entry in preload["frontmatter"]:
                used = any(_path_in_pattern(cited, entry["path"]) for cited in cited_paths_fm)
                if not used:
                    candidates.append(PruneCandidate(
                        role_file=rel_role,
                        role_name=role_name,
                        preload_path=entry["raw_line_path"],
                        tier="frontmatter",
                        reason=f"no pages under this pattern cited in last {frontmatter_threshold} sessions",
                        detail={"sessions_examined": len(sessions_fm)},
                        in_capability_block=entry["in_capability_block"],
                    ))

    return candidates


def _remove_preload_line(role_text: str, target_path: str, *, tier: str) -> tuple[str, bool]:
    """
    Remove the first preload list-item that matches `target_path` from the appropriate
    section. Skips lines inside `# capability:` blocks. Returns (new_text, removed).
    """
    section_heading = (
        "preload context (full)" if tier == "full" else "preload context (frontmatter only)"
    )
    target_norm = _normalize_path(target_path)
    line_pat = re.compile(r"^(\s*)(?:\d+\.|-)\s+(.+?)\s*$")

    lines = role_text.splitlines()
    result: list[str] = []
    in_section = False
    in_capability_block = False
    removed = False

    for line in lines:
        if line.startswith("## "):
            heading = line.lstrip("#").strip().lower()
            in_section = heading.startswith(section_heading)
            in_capability_block = False
            result.append(line)
            continue
        stripped = line.strip()
        if stripped.startswith("# capability:"):
            in_capability_block = True
            result.append(line)
            continue
        if stripped.startswith("# end capability:"):
            in_capability_block = False
            result.append(line)
            continue

        if removed or not in_section or in_capability_block:
            result.append(line)
            continue

        m = line_pat.match(line)
        if not m:
            result.append(line)
            continue
        content = m.group(2)
        content = re.sub(r"\s+#.*$", "", content).strip().strip("`")
        if not content.startswith("/"):
            result.append(line)
            continue
        if _normalize_path(content) == target_norm:
            removed = True
            continue  # skip this line
        result.append(line)

    new_text = "\n".join(result)
    if role_text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, removed


def plan_prune(
    candidates: list[PruneCandidate], repo_root: Path
) -> Plan:
    """Build a plan to apply the given prune candidates (one role file at a time)."""
    plan = Plan(operation=f"prune ({len(candidates)} candidates)")

    # Group by role_file
    by_role: dict[str, list[PruneCandidate]] = {}
    for c in candidates:
        if c.in_capability_block:
            plan.warnings.append(
                f"skipping {c.role_file}::{c.preload_path}: managed by `{c.detail.get('capability') or '#'}` "
                f"capability marker — use `/framework disable` instead"
            )
            continue
        by_role.setdefault(c.role_file, []).append(c)

    for rel, group in by_role.items():
        path = repo_root / rel
        if not path.is_file():
            plan.warnings.append(f"role file missing: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        applied = []
        for c in group:
            text, removed = _remove_preload_line(text, c.preload_path, tier=c.tier)
            if removed:
                applied.append(c.preload_path)
            else:
                plan.warnings.append(
                    f"could not find {c.preload_path} in {rel} (already removed?)"
                )
        if text != original:
            plan.changes.append(Change(
                kind="edit",
                path=rel,
                description=f"Remove {len(applied)} preload entries: {', '.join(applied)}",
                new_content=text,
            ))

    return plan


def format_prune_candidates(candidates: list[PruneCandidate]) -> str:
    """Human-readable display of prune candidates, grouped by role."""
    if not candidates:
        return "No prune candidates."

    by_role: dict[str, list[PruneCandidate]] = {}
    for c in candidates:
        by_role.setdefault(f"{c.role_name} ({c.role_file})", []).append(c)

    lines = [f"Prune candidates across {len(by_role)} role(s):", ""]
    for role_key, group in sorted(by_role.items()):
        lines.append(f"  {role_key}")
        for c in group:
            marker = "  [capability-managed]" if c.in_capability_block else ""
            lines.append(f"    [{c.tier}] {c.preload_path}{marker}")
            lines.append(f"       reason: {c.reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --- Status ---

def status(repo_root: Path, config: dict) -> dict:
    """Return current capability and lint visibility state."""
    capabilities = config.get("capabilities", {})
    lint = config.get("lint", {})
    return {
        "capabilities": {cap: capabilities.get(cap, False) for cap in sorted(KNOWN_CAPABILITIES)},
        "lint_warnings_visible": {
            rule: lint.get("warnings_visible", {}).get(rule, False)
            for rule in sorted(CONFIGURABLE_LINT_RULES)
        },
        "lint_thresholds": {
            k: v for k, v in lint.items()
            if k not in ("warnings_visible",) and not k.startswith("_")
        },
    }


def format_status(state: dict) -> str:
    """Human-readable status report."""
    lines = ["Framework status:", ""]
    lines.append("  Capabilities:")
    for cap, on in state["capabilities"].items():
        marker = "✓" if on else " "
        lines.append(f"    [{marker}] {cap}")
    lines.append("")
    lines.append("  Lint warning visibility:")
    visible = [r for r, on in state["lint_warnings_visible"].items() if on]
    shadowed = [r for r, on in state["lint_warnings_visible"].items() if not on]
    if visible:
        for rule in visible:
            lines.append(f"    [✓] {rule} (visible)")
    if shadowed:
        for rule in shadowed:
            lines.append(f"    [ ] {rule} (shadow)")
    return "\n".join(lines)


# --- CLI ---

def main() -> int:
    parser = argparse.ArgumentParser(description="Framework capability and lint visibility engine.")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="show plan without applying")
    parser.add_argument("--json", action="store_true", help="output JSON")

    sub = parser.add_subparsers(dest="cmd", required=False)

    p_enable = sub.add_parser("enable", help="enable a capability")
    p_enable.add_argument("capability")

    p_disable = sub.add_parser("disable", help="disable a capability")
    p_disable.add_argument("capability")

    p_enable_lint = sub.add_parser("enable-lint", help="make a shadow lint warning visible")
    p_enable_lint.add_argument("rule")

    p_disable_lint = sub.add_parser("disable-lint", help="shadow a previously visible lint warning")
    p_disable_lint.add_argument("rule")

    p_prune = sub.add_parser("prune", help="list/apply prune candidates for role preloads")
    p_prune.add_argument("role", nargs="?", help="restrict to this role name")
    p_prune.add_argument("--apply", action="store_true", help="apply the suggested removals")

    sub.add_parser("lint-status", help="show lint visibility status")
    sub.add_parser("status", help="show current capability + lint state")

    args = parser.parse_args()

    try:
        repo_root = args.repo.resolve() if args.repo else find_repo_root()
    except RuntimeError as e:
        print(f"framework: {e}", file=sys.stderr)
        return 3

    try:
        config = load_config(repo_root)
    except RuntimeError as e:
        print(f"framework: {e}", file=sys.stderr)
        return 3

    # No subcommand → show status
    if args.cmd is None or args.cmd == "status":
        state = status(repo_root, config)
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(format_status(state))
        return 0

    if args.cmd == "lint-status":
        state = status(repo_root, config)
        # Lint visibility only
        lint_state = {
            "lint_warnings_visible": state["lint_warnings_visible"],
            "lint_thresholds": state["lint_thresholds"],
        }
        if args.json:
            print(json.dumps(lint_state, indent=2))
        else:
            print(format_status({"capabilities": {}, **lint_state}))
        return 0

    # Build the appropriate plan
    if args.cmd == "enable":
        plan = plan_enable(args.capability, repo_root, config)
    elif args.cmd == "disable":
        plan = plan_disable(args.capability, repo_root, config)
    elif args.cmd == "enable-lint":
        plan = plan_enable_lint(args.rule, repo_root, config)
    elif args.cmd == "disable-lint":
        plan = plan_disable_lint(args.rule, repo_root, config)
    elif args.cmd == "prune":
        candidates = find_prune_candidates(repo_root, config, role_filter=args.role)
        if not args.apply:
            # Just list candidates
            if args.json:
                print(json.dumps([c.to_dict() for c in candidates], indent=2))
            else:
                print(format_prune_candidates(candidates))
            return 0
        # Apply the prunes
        plan = plan_prune(candidates, repo_root)
    else:
        print(f"framework: unknown command: {args.cmd}", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        _print_plan_summary(plan)

    if plan.error:
        return 1

    if args.dry_run:
        return 0

    if not plan.changes and not plan.config_updates:
        return 0

    try:
        apply_plan(plan, repo_root)
    except FrameworkError as e:
        print(f"framework: apply failed: {e}", file=sys.stderr)
        return 2

    if not args.json:
        print()
        print("Applied successfully.")
    return 0


def _print_plan_summary(plan: Plan) -> None:
    print(f"Plan: {plan.operation}")
    if plan.error:
        print(f"  ERROR: {plan.error}")
        return
    if not plan.changes and not plan.config_updates:
        print("  (no changes needed)")
    else:
        print(f"  Changes ({len(plan.changes)}):")
        for change in plan.changes:
            print(f"    [{change.kind}] {change.path}")
            print(f"      {change.description}")
        if plan.config_updates:
            print(f"  Config updates:")
            for key, value in plan.config_updates.items():
                print(f"    {key} = {value}")
    if plan.warnings:
        print("  Warnings:")
        for w in plan.warnings:
            print(f"    - {w}")


if __name__ == "__main__":
    raise SystemExit(main())
