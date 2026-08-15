"""
CLI over the commons twin-map / link-rewrite helpers in common.py.

Used by the /amend-commons and /promote skills to inspect the twin map and to
preview/apply rewrites of a commons page's body wikilinks to their commons
twins (propose-for-review: dry run by default).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import (  # noqa: E402
    build_twin_resolver,
    commons_twin_map,
    find_repo_root,
    parse_frontmatter,
    rewrite_links_to_twins,
)


def _cmd_twins(repo_root: Path, _args) -> int:
    m = commons_twin_map(repo_root)
    if not m:
        print("(no commons twins)")
        return 0
    for area_id in sorted(m):
        print(f"{area_id} -> {m[area_id]}")
    return 0


def _cmd_rewrite(repo_root: Path, args) -> int:
    page = Path(args.page).resolve()
    if not page.is_file():
        print(f"commons_links: no such file: {page}", file=sys.stderr)
        return 1
    text = page.read_text(encoding="utf-8")
    _fm, body = parse_frontmatter(text)
    new_body, changes = rewrite_links_to_twins(body, build_twin_resolver(repo_root))
    if not changes:
        print("no links to rewrite (no cited page has a commons twin).")
        return 0
    print("proposed link rewrites:")
    for old, new in changes:
        print(f"  [[{old}]] -> [[{new}]]")
    if args.apply:
        head = text[: len(text) - len(body)]
        page.write_text(head + new_body, encoding="utf-8")
        print(f"applied {len(changes)} rewrite(s).")
    else:
        print("(dry run — pass --apply to write)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect/apply commons twin links.")
    parser.add_argument("--repo", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("twins", help="print the area-id -> commons-id twin map")
    p_rw = sub.add_parser("rewrite", help="rewrite a commons page's body links to their twins")
    p_rw.add_argument("page", help="path to the commons page")
    p_rw.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = parser.parse_args()

    try:
        repo_root = args.repo.resolve() if args.repo else find_repo_root()
    except RuntimeError as e:
        print(f"commons_links: {e}", file=sys.stderr)
        return 2

    if args.cmd == "twins":
        return _cmd_twins(repo_root, args)
    if args.cmd == "rewrite":
        return _cmd_rewrite(repo_root, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
