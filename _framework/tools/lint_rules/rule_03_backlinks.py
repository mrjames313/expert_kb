"""
Rule 3 — Backlink synchronization (fixup).

Regenerates <page>.links.json sidecars containing links_in/links_out from
the current state of forward links across the kb. Runs in the fixup phase
of lint — it modifies files and only produces findings on write failures.

The sidecar format:
    {
      "links_in": ["areas/.../kb/findings/f-...md", ...],
      "links_out": ["areas/.../kb/sources/s-...md", ...]
    }
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

from common import (
    Finding,
    build_wikilink_index,
    extract_wikilinks,
    iter_kb_pages,
    parse_frontmatter,
    split_wikilink,
)

RULE_ID = "rule_03"
SEVERITY = "error"


def check(repo_root: Path, config: dict) -> list[Finding]:
    """Regenerate sidecars. Returns findings only on write failures."""
    findings: list[Finding] = []
    index = build_wikilink_index(repo_root)

    # Forward edges: from path -> set of resolved-target paths
    out_edges: dict[Path, set[Path]] = defaultdict(set)
    # Reverse edges: target path -> set of source paths
    in_edges: dict[Path, set[Path]] = defaultdict(set)

    for page in iter_kb_pages(repo_root):
        try:
            text = page.read_text(encoding="utf-8")
            _fm, body = parse_frontmatter(text)
        except (OSError, yaml.YAMLError):
            continue  # other rules flag

        for raw in extract_wikilinks(body):
            _prefix, target = split_wikilink(raw)
            resolved = index.get(target)
            if resolved is None:
                continue  # rule 2 flags unresolved links
            out_edges[page].add(resolved)
            in_edges[resolved].add(page)

    # Write sidecars for every kb page (so even orphans get one with empty lists)
    for page in iter_kb_pages(repo_root):
        sidecar = page.with_suffix(".md.links.json")
        # Skip — actually we want .links.json next to .md, so e.g. foo.md -> foo.md.links.json
        # Hmm, .with_suffix would give us .links.json (replacing .md). Let me use a different approach.
        sidecar = page.parent / f"{page.name}.links.json"

        payload = {
            "links_out": sorted(str(p.relative_to(repo_root)) for p in out_edges.get(page, set())),
            "links_in": sorted(str(p.relative_to(repo_root)) for p in in_edges.get(page, set())),
        }

        try:
            sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as e:
            findings.append(
                Finding(
                    RULE_ID,
                    SEVERITY,
                    str(page.relative_to(repo_root)),
                    f"could not write backlink sidecar: {e}",
                )
            )

    return findings
