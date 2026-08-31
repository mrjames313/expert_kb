"""
Helpers for lint rule tests. Build minimal repo trees with kb pages
that have specific frontmatter / link patterns.
"""

from __future__ import annotations

import textwrap
from pathlib import Path


def write_kb_page(
    repo_root: Path,
    area: str,
    page_type: str,
    slug: str,
    *,
    frontmatter_overrides: dict | None = None,
    body: str = "",
    extra_frontmatter_yaml: str | None = None,
) -> Path:
    """
    Create a kb page under the given area with valid default frontmatter,
    plus any overrides. `area` is either "commons" or "areas/<name>".

    Returns the path to the created file.
    """
    prefix_by_type = {"source": "s", "concept": "c", "finding": "f", "decision": "d"}
    type_dir_by_type = {
        "source": "sources",
        "concept": "concepts",
        "finding": "findings",
        "decision": "decisions",
    }

    if page_type not in prefix_by_type:
        raise ValueError(f"unsupported page type: {page_type}")

    page_id = f"{prefix_by_type[page_type]}-2026-05-{slug}"
    filename = f"{page_id}.md"

    if area == "commons":
        kb_dir = repo_root / "commons" / "kb" / type_dir_by_type[page_type]
        area_value = "commons"
    else:
        kb_dir = repo_root / area / "kb" / type_dir_by_type[page_type]
        # area in frontmatter is the path under areas/, e.g. "research/optics"
        area_value = area.replace("areas/", "", 1)
    kb_dir.mkdir(parents=True, exist_ok=True)

    defaults = {
        "source": {"status": "active", "provenance": "  kind: external\n  retrieved: 2026-05-01\n  raw_path: ~"},
        "concept": {"status": "developing"},
        "finding": {"status": "active", "provenance": "  kind: experiment"},
        "decision": {"status": "active", "alternatives_considered": "[]"},
    }
    type_specifics = defaults[page_type]

    fm: dict = {
        "id": page_id,
        "title": f"Test {page_type} {slug}",
        "type": page_type,
        "status": type_specifics["status"],
        "area": area_value,
        "created": "2026-05-08",
        "updated": "2026-05-08",
        "summary": f"Test {page_type} page for {slug}.",
    }
    if page_type != "source":  # source pages don't carry relevant_to mandatorily; keep simple
        fm["relevant_to"] = ["test"]
    if frontmatter_overrides:
        fm.update(frontmatter_overrides)

    # Build YAML frontmatter manually so test-specific overrides like
    # `evidence: ["[[c-foo]]"]` come through cleanly.
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for sk, sv in v.items():
                lines.append(f"  {sk}: {sv}")
        elif v is None:
            lines.append(f"{k}: ~")
        else:
            lines.append(f"{k}: {v}")

    # type-specific frontmatter blocks (raw YAML so we can do nested)
    if page_type == "source":
        lines.append("provenance:")
        for line in type_specifics["provenance"].split("\n"):
            lines.append(line)
    elif page_type == "finding" and "provenance" not in (frontmatter_overrides or {}):
        lines.append("provenance:")
        for line in type_specifics["provenance"].split("\n"):
            lines.append(line)
    elif page_type == "decision" and "alternatives_considered" not in (frontmatter_overrides or {}):
        lines.append(f"alternatives_considered: {type_specifics['alternatives_considered']}")

    if extra_frontmatter_yaml:
        lines.append(extra_frontmatter_yaml.rstrip("\n"))

    lines.append("---")
    lines.append("")
    lines.append(body)

    content = "\n".join(lines) + "\n"
    page_path = kb_dir / filename
    page_path.write_text(content, encoding="utf-8")
    return page_path


def write_exchange(
    repo_root: Path,
    slug: str,
    *,
    kind: str = "query",
    from_area: str = "engineering",
    from_role: str = "hardware-engineer",
    to_area: str = "research",
    status: str = "open",
    created: str = "2026-05-08",
    body: str | None = None,
    dir_name: str | None = None,
    filename: str | None = None,
    overrides: dict | None = None,
    drop: tuple[str, ...] = (),
) -> Path:
    """Create an exchange file under `exchanges/<a>--<b>/`.

    The field set and body headings are copied from the templates in
    `.claude/skills/exchange/SKILL.md` step 5 (and `exchange-protocol.md`), NOT
    from what the rule module happens to read — an exchange file is written by a
    skill, so its shape is a contract between two documents, and a fixture taken
    from the implementation could only ever assert that the code still does what
    it did. See `maintaining.md` → "Test fixtures come from the contract".

    `overrides` sets or replaces frontmatter fields; `drop` removes them.
    """
    exchange_id = f"ex-{created}-{slug}"

    fm: dict = {
        "id": exchange_id,
        "kind": kind,
        "status": status,
        "from_area": from_area,
        "from_role": from_role,
        "to_area": to_area,
        "created": created,
    }
    if kind == "brief":
        fm["to_roles"] = ["hardware-engineer", "firmware-engineer"]
        fm["open_for"] = ["hardware-engineer", "firmware-engineer"]
    fm["relevant_to"] = ["thermal budget"]

    if overrides:
        fm.update(overrides)
    for key in drop:
        fm.pop(key, None)

    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(str(i) for i in v)}]" if v else f"{k}: []")
        elif v is None:
            lines.append(f"{k}: ~")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")

    if body is None:
        if kind == "brief":
            body = (
                "# Brief\nThe drift model now predicts ~2x the responsivity swing at 85 C.\n\n"
                "# Dispositions\n_(each targeted role records what it did on close)_\n"
            )
        else:
            body = (
                "# Question\nWhat's the temperature dependence of responsivity?\n\n"
                "# Response\n_(filled in by responder)_\n"
            )
    lines.append(body)

    if dir_name is None:
        dir_name = "--".join(sorted(a.replace("/", "-") for a in (from_area, to_area)))
    ex_dir = repo_root / "exchanges" / dir_name
    ex_dir.mkdir(parents=True, exist_ok=True)
    path = ex_dir / (filename or f"{exchange_id}.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with _framework/config.yml so find_repo_root and load_config work."""
    framework = tmp_path / "_framework"
    framework.mkdir()
    (framework / "config.yml").write_text(
        textwrap.dedent("""
        capabilities:
          multi_area: false
          por: false
          task_subagents: false
          formal_review: false
        lint:
          pulse_line_cap: 80
          shadow_suggest_threshold: 5
          warnings_visible: {}
        prune:
          full_tier_stale_sessions: 10
          frontmatter_tier_stale_sessions: 30
        """).lstrip()
    )
    (tmp_path / "commons").mkdir()
    (tmp_path / "commons" / "kb").mkdir()
    (tmp_path / "areas").mkdir()
    return tmp_path
