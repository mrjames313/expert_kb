"""
Rule 22 — Exchange frontmatter validity.

Exchange files carry a schema of their own, sharing only three field names with
a kb page — so Rule 1 cannot be pointed at them (it would emit five spurious
"missing required field" errors on every well-formed exchange). This is that
rule.

Checked, per `_framework/schema/exchange-protocol.md`:
- frontmatter is present and parses as a mapping
- `kind` is `query` or `brief`
- the fields both kinds require are present, plus `to_roles`/`open_for` on a brief
- `status` is drawn from the vocabulary for its kind — the two differ, and a
  brief has no answer cycle
- a query carries no `to_roles`/`open_for` (the usual cause is a brief filed
  under the wrong kind, which routes it to the wrong disposal command)
- `open_for` is a subset of `to_roles`, since it is drained from that snapshot
- a brief is `closed` exactly when `open_for` is empty — asserted by the
  protocol, checked nowhere until now
- `id` matches `ex-YYYY-MM-DD-<slug>` and agrees with the filename
- `created` is an ISO date
- the parties differ, and the directory name is the canonical one for the pair

The last of these is what keeps an exchange *findable*: `/start`, `/kb-vitals`,
`/respond-exchange` and `/close-exchange` all glob exactly one level
(`exchanges/*/`), so a file in a directory named anything else is not an error
anywhere — it simply never surfaces to the role that owes it a response.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from common import (
    Finding,
    exchange_dir_name,
    is_iso_date,
    iter_exchange_files,
    parse_frontmatter,
)

RULE_ID = "rule_22"
SEVERITY = "error"

VALID_KINDS = {"query", "brief"}

# Both kinds. `relevant_to` is deliberately absent: it is an ordering
# convention in frontmatter.md, not a required field, and kb pages don't
# require it either — an exchange should not be held to a stricter bar.
REQUIRED_FIELDS_ALL = ("id", "kind", "status", "from_area", "from_role", "to_area", "created")
REQUIRED_FIELDS_BRIEF = ("to_roles", "open_for")

# A query has an answer cycle; a brief has dispositions instead.
VALID_STATUSES_BY_KIND = {
    "query": {"open", "answered", "follow_up", "closed"},
    "brief": {"open", "closed"},
}

_EXCHANGE_ID_RE = re.compile(r"^ex-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")


def _as_role_list(value: object) -> list[str] | None:
    """A `to_roles`/`open_for` value as a list of names, or None if it isn't a
    list. YAML gives `[]` as an empty list and a bare `~` as None — an empty
    `open_for` is meaningful (it means the brief is done), so None is the only
    shape treated as malformed."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return None


def _check_exchange(path: Path, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(path.relative_to(repo_root))

    def flag(message: str, suggestion: str | None = None) -> None:
        findings.append(Finding(RULE_ID, SEVERITY, rel, message, line=1, suggestion=suggestion))

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        flag(f"could not read file: {e}")
        return findings

    try:
        fm, _body = parse_frontmatter(text)
    except yaml.YAMLError as e:
        flag(f"malformed frontmatter: {e}")
        return findings

    if fm is None:
        flag("missing frontmatter block")
        return findings

    kind = fm.get("kind")
    if kind is None:
        flag("missing required frontmatter field: kind")
    elif kind not in VALID_KINDS:
        flag(
            f"invalid kind: {kind!r}",
            suggestion=f"valid kinds: {', '.join(sorted(VALID_KINDS))}",
        )

    required = list(REQUIRED_FIELDS_ALL)
    if kind == "brief":
        required.extend(REQUIRED_FIELDS_BRIEF)
    for field_name in required:
        if field_name not in fm:
            flag(f"missing required frontmatter field: {field_name}")

    # A query with brief-only fields is nearly always a brief filed under the
    # wrong kind — which sends it to /respond-exchange, where nobody owes it
    # an answer, instead of to its targeted roles' /close-exchange.
    if kind == "query":
        for field_name in REQUIRED_FIELDS_BRIEF:
            if field_name in fm:
                flag(
                    f"query carries brief-only field {field_name!r}",
                    suggestion="queries are answerable by any role in to_area; "
                    "if specific roles are targeted, this is `kind: brief`",
                )

    status = fm.get("status")
    if status is not None and kind in VALID_STATUSES_BY_KIND:
        valid = VALID_STATUSES_BY_KIND[kind]
        if status not in valid:
            flag(
                f"invalid status {status!r} for kind {kind!r}",
                suggestion=f"valid statuses for {kind}: {', '.join(sorted(valid))}",
            )

    if kind == "brief":
        to_roles = _as_role_list(fm.get("to_roles"))
        open_for = _as_role_list(fm.get("open_for"))
        if "to_roles" in fm and to_roles is None:
            flag("to_roles must be a list of role names")
        if "open_for" in fm and open_for is None:
            flag("open_for must be a list of role names")
        if to_roles is not None and open_for is not None:
            stray = [r for r in open_for if r not in to_roles]
            if stray:
                flag(
                    f"open_for names role(s) not in to_roles: {', '.join(sorted(stray))}",
                    suggestion="open_for is drained from the to_roles snapshot taken at file "
                    "time; a role that was never targeted cannot owe a disposition",
                )
            # The protocol's own invariant: a brief closes exactly when the last
            # targeted role has disposed of it.
            if status in ("open", "closed"):
                if status == "closed" and open_for:
                    flag(
                        "status is 'closed' but open_for still names "
                        f"{', '.join(open_for)}",
                        suggestion="a brief closes only when open_for is empty; "
                        "set status back to 'open' or record the outstanding dispositions",
                    )
                elif status == "open" and not open_for:
                    flag(
                        "status is 'open' but open_for is empty",
                        suggestion="every targeted role has disposed of this brief; set status to 'closed'",
                    )

    exchange_id = fm.get("id")
    if exchange_id is not None:
        if not _EXCHANGE_ID_RE.match(str(exchange_id)):
            flag(
                f"id {exchange_id!r} does not match convention",
                suggestion="expected pattern: ex-YYYY-MM-DD-<slug>",
            )
        elif str(exchange_id) != path.stem:
            flag(
                f"id {exchange_id!r} does not match filename {path.name!r}",
                suggestion=f"rename the file to {exchange_id}.md, or correct the id",
            )

    created = fm.get("created")
    if created is not None and not is_iso_date(created):
        flag(f"created must be YYYY-MM-DD, got {created!r}")

    from_area = fm.get("from_area")
    to_area = fm.get("to_area")
    if from_area is not None and to_area is not None:
        if from_area == to_area:
            flag(
                f"from_area and to_area are both {from_area!r}",
                suggestion="an exchange crosses an area boundary; "
                "within one area, write to the area's own kb",
            )
        else:
            expected = exchange_dir_name(str(from_area), str(to_area))
            actual = path.parent.name
            if actual != expected:
                flag(
                    f"exchange between {from_area!r} and {to_area!r} is filed in "
                    f"'exchanges/{actual}/', not 'exchanges/{expected}/'",
                    suggestion="one canonical directory per pair, areas sorted "
                    "alphabetically and joined by '--' (a sub-area's slash becomes '-'); "
                    "every consumer globs exchanges/*/, so a file elsewhere never surfaces",
                )

    return findings


def check(repo_root: Path, config: dict) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_exchange_files(repo_root):
        findings.extend(_check_exchange(path, repo_root))
    return findings
