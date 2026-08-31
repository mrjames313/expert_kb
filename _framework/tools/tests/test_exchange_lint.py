"""
Tests for exchange-file lint coverage.

Exchanges were the last live surface no rule walked: `common.py` had no
iterator, so Rules 1, 2 and 5 never saw them, while `/respond-exchange` told the
responder to run lint *because* the wikilinks in their answer must resolve.
This file covers the iterator, the two rules that now walk it, the exchange
frontmatter rule (22), and Rule 15's regeneration of the pair index.

Fixtures come from `.claude/skills/exchange/SKILL.md` and
`exchange-protocol.md`, not from the rule modules — see `write_exchange`.
"""

from __future__ import annotations

from pathlib import Path

from common import exchange_dir_name, iter_exchange_files
from lint_rules import (
    rule_02_forward_links,
    rule_05_supersession,
    rule_15_index,
    rule_22_exchange_frontmatter,
)

from lint_helpers import make_minimal_repo, write_exchange, write_kb_page


DEFAULT_CONFIG = {"lint": {"pulse_line_cap": 80}}


def _messages(findings, rule_id: str | None = None) -> list[str]:
    return [f.message for f in findings if rule_id is None or f.rule_id == rule_id]


# --- The iterator ---

class TestIterExchangeFiles:
    def test_finds_exchange_files(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal-sensitivity")
        assert [p.name for p in iter_exchange_files(tmp_path)] == [
            "ex-2026-05-08-thermal-sensitivity.md"
        ]

    def test_ex_prefix_is_the_contract(self, tmp_path: Path) -> None:
        """`/exchange` names files `ex-<date>-<slug>.md`. This prefix has broken
        once already — `kb_vitals` globbed the long-dead `q-*` form and returned
        zero for every project with multi_area on — so it is pinned here."""
        make_minimal_repo(tmp_path)
        ex_dir = tmp_path / "exchanges" / "engineering--research"
        ex_dir.mkdir(parents=True)
        (ex_dir / "q-2026-05-08-old-form.md").write_text("---\nid: q-1\n---\n")
        assert list(iter_exchange_files(tmp_path)) == []

    def test_skips_index_readme_and_owners(self, tmp_path: Path) -> None:
        """The `ex-` restriction excludes the directory's furniture without
        having to enumerate it — including the index Rule 15 generates, which
        would otherwise be linted as if an agent had written it."""
        make_minimal_repo(tmp_path)
        path = write_exchange(tmp_path, "thermal-sensitivity")
        for name in ("index.md", "README.md", "OWNERS"):
            (path.parent / name).write_text("not an exchange\n")
        assert [p.name for p in iter_exchange_files(tmp_path)] == [path.name]

    def test_no_exchanges_directory_is_not_an_error(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        assert list(iter_exchange_files(tmp_path)) == []


class TestExchangeDirName:
    def test_areas_sort_alphabetically_regardless_of_direction(self) -> None:
        assert exchange_dir_name("research", "engineering") == "engineering--research"
        assert exchange_dir_name("engineering", "research") == "engineering--research"

    def test_sub_area_slash_becomes_a_hyphen(self) -> None:
        """A sub-area id carries a slash, which would nest the directory a level
        deeper — and every consumer (`/start`, `/kb-vitals`, `/respond-exchange`,
        `/close-exchange`) globs exactly `exchanges/*/`. A nested exchange is not
        an error anywhere; it simply never surfaces to the role that owes it a
        response."""
        assert exchange_dir_name("engineering", "research/optics") == "engineering--research-optics"
        assert "/" not in exchange_dir_name("a/b/c", "d/e")


# --- Rule 2 on exchanges ---

class TestRule02Exchanges:
    def test_context_wikilink_must_resolve(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\n[[research:findings/f-2026-05-nope]]\n",
        )
        assert any("does not resolve" in m for m in _messages(
            rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG), "rule_02"))

    def test_resolving_context_wikilink_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "drift-model")
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\n[[research:findings/f-2026-05-drift-model]]\n",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert [f for f in findings if "exchanges/" in f.file_path] == []

    def test_wrong_area_prefix_is_an_error(self, tmp_path: Path) -> None:
        """The area prefix is the whole point of a `## Context` section — it
        shows the reader which boundary the exchange crosses."""
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "drift-model")
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\n[[engineering:findings/f-2026-05-drift-model]]\n",
        )
        assert any("declares area" in m for m in _messages(
            rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG), "rule_02"))

    def test_wikilink_to_a_spec_file_is_an_error(self, tmp_path: Path) -> None:
        """`exchange-protocol.md`'s own example Context section used to contain
        `[[specs/2026-05-detector-thermal/brief]]` — a wikilink to a file outside
        `kb/`, which can never resolve. It was the example an agent copies."""
        make_minimal_repo(tmp_path)
        spec = tmp_path / "areas" / "engineering" / "specs" / "2026-05-detector-thermal"
        spec.mkdir(parents=True)
        (spec / "brief.md").write_text("# Brief\n")
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\n[[specs/2026-05-detector-thermal/brief]]\n",
        )
        assert any("does not resolve" in m for m in _messages(
            rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG), "rule_02"))

    def test_relative_markdown_link_to_a_spec_resolves(self, tmp_path: Path) -> None:
        """...and this is the form that replaced it."""
        make_minimal_repo(tmp_path)
        spec = tmp_path / "areas" / "engineering" / "specs" / "2026-05-detector-thermal"
        spec.mkdir(parents=True)
        (spec / "brief.md").write_text("# Brief\n")
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\nspec "
                 "[brief](../../areas/engineering/specs/2026-05-detector-thermal/brief.md)\n",
        )
        findings = rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG)
        assert [f for f in findings if "exchanges/" in f.file_path] == []

    def test_broken_relative_markdown_link_is_an_error(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n## Context\n[gone](../../areas/engineering/specs/nope/brief.md)\n",
        )
        assert any("does not resolve to an existing file" in m for m in _messages(
            rule_02_forward_links.check(tmp_path, DEFAULT_CONFIG), "rule_02"))


# --- Rule 5 on exchanges ---

class TestRule05Exchanges:
    def test_citing_a_superseded_page_is_an_error(self, tmp_path: Path) -> None:
        """An answer that hands another area a retired finding is the same
        defect as a page that cites one — and worse, since the receiving area
        may preload it on the strength of the exchange."""
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "new")
        write_kb_page(
            tmp_path, "areas/research", "finding", "old",
            frontmatter_overrides={
                "status": "superseded",
                "superseded_by": "findings/f-2026-05-new",
            },
        )
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n# Response\nSee [[research:findings/f-2026-05-old]].\n",
        )
        findings = rule_05_supersession.check(tmp_path, DEFAULT_CONFIG)
        assert any("exchanges/" in f.file_path and "superseded" in f.message
                   for f in findings)

    def test_citing_a_live_page_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "finding", "live")
        write_exchange(
            tmp_path, "thermal",
            body="# Question\nWhy?\n\n# Response\nSee [[research:findings/f-2026-05-live]].\n",
        )
        findings = rule_05_supersession.check(tmp_path, DEFAULT_CONFIG)
        assert [f for f in findings if "exchanges/" in f.file_path] == []


# --- Rule 22: exchange frontmatter ---

class TestRule22ExchangeFrontmatter:
    def test_protocol_shaped_query_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", kind="query")
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_protocol_shaped_brief_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       from_role="optics-researcher", to_area="engineering")
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_kb_page_fields_are_not_required(self, tmp_path: Path) -> None:
        """Rule 1 could not simply be pointed at exchanges: only three of its
        eight required fields exist here, so it would emit five spurious
        `missing required field` errors on every well-formed exchange."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        messages = _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG))
        for absent in ("title", "type", "area", "updated", "summary"):
            assert not any(absent in m for m in messages)

    def test_relevant_to_is_not_required(self, tmp_path: Path) -> None:
        """It is a field-ordering convention in `frontmatter.md`, not a required
        field — kb pages don't require it either."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", drop=("relevant_to",))
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_missing_required_field_is_an_error(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", drop=("from_role",))
        assert any("missing required frontmatter field: from_role" in m
                   for m in _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_brief_requires_to_roles_and_open_for(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", drop=("to_roles", "open_for"))
        messages = _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG))
        assert any("to_roles" in m for m in messages)
        assert any("open_for" in m for m in messages)

    def test_invalid_kind_is_an_error(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", kind="memo")
        assert any("invalid kind" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_query_status_vocabulary(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        for status in ("open", "answered", "follow_up", "closed"):
            # slug, not status: ids are kebab-case, so the underscore comes out
            write_exchange(tmp_path, f"q-{status.replace('_', '-')}", status=status)
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_brief_cannot_take_a_query_status(self, tmp_path: Path) -> None:
        """A brief has no answer cycle, so `answered` is meaningless on one."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", status="answered")
        assert any("invalid status 'answered' for kind 'brief'" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_query_with_brief_only_fields_is_an_error(self, tmp_path: Path) -> None:
        """Usually a brief filed under the wrong kind, which routes it to
        /respond-exchange — where nobody owes it an answer."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", overrides={"to_roles": ["hardware-engineer"]})
        assert any("brief-only field" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_open_for_must_be_a_subset_of_to_roles(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering",
                       overrides={"to_roles": ["hardware-engineer"],
                                  "open_for": ["hardware-engineer", "stranger"]})
        assert any("not in to_roles" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_closed_brief_must_have_empty_open_for(self, tmp_path: Path) -> None:
        """The protocol asserts this invariant and nothing checked it."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", status="closed")
        assert any("open_for still names" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_drained_open_for_must_close_the_brief(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", overrides={"open_for": []})
        assert any("open_for is empty" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_fully_disposed_brief_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", status="closed",
                       overrides={"open_for": []})
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_id_must_match_the_filename(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", filename="ex-2026-05-08-other.md")
        assert any("does not match filename" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_id_convention(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", overrides={"id": "ex-thermal"},
                       filename="ex-2026-05-08-thermal.md")
        assert any("does not match convention" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_created_must_be_an_iso_date(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", overrides={"created": "May 8th"})
        assert any("created must be YYYY-MM-DD" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_parties_must_differ(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", to_area="engineering")
        assert any("both 'engineering'" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_misfiled_directory_is_an_error(self, tmp_path: Path) -> None:
        """One canonical directory per pair. A file elsewhere is invisible to
        every consumer, so without this check it fails silently."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", dir_name="research--engineering")
        assert any("is filed in" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))

    def test_sub_area_exchange_in_the_slugified_directory_is_clean(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", to_area="research/optics")
        assert rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG) == []

    def test_malformed_frontmatter_is_reported(self, tmp_path: Path) -> None:
        """Rule 15 skips a file it cannot parse, so without this the file would
        simply vanish from its index rather than announce itself."""
        make_minimal_repo(tmp_path)
        path = write_exchange(tmp_path, "thermal")
        path.write_text("---\nid: [unclosed\n---\n\n# Question\nWhy?\n")
        messages = _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG))
        assert any("malformed frontmatter" in m for m in messages)

    def test_missing_frontmatter_is_reported(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        path = write_exchange(tmp_path, "thermal")
        path.write_text("# Question\nNo frontmatter at all.\n")
        assert any("missing frontmatter block" in m for m in
                   _messages(rule_22_exchange_frontmatter.check(tmp_path, DEFAULT_CONFIG)))


# --- Rule 15: exchange index regeneration ---

class TestRule15ExchangeIndex:
    def _index(self, tmp_path: Path, dir_name: str = "engineering--research") -> str:
        return (tmp_path / "exchanges" / dir_name / "index.md").read_text()

    def test_index_is_generated(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        index = self._index(tmp_path)
        assert "Auto-generated; do not edit by hand." in index
        assert "ex-2026-05-08-thermal" in index

    def test_entries_are_relative_markdown_links_not_wikilinks(self, tmp_path: Path) -> None:
        """`exchange-protocol.md` used to specify the index line as
        `- [[<id>]] — …`. Only kb pages are in the wikilink index, so that form
        could never resolve — and turning Rule 2 on would have flagged every
        line of every index."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        index = self._index(tmp_path)
        assert "[[" not in index
        assert "[ex-2026-05-08-thermal](ex-2026-05-08-thermal.md)" in index

    def test_index_links_resolve_under_rule_02(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        index_path = tmp_path / "exchanges" / "engineering--research" / "index.md"
        for line in index_path.read_text().splitlines():
            if line.startswith("- ["):
                target = line.split("](", 1)[1].split(")", 1)[0]
                assert (index_path.parent / target).is_file()

    def test_status_grouping_comes_from_frontmatter(self, tmp_path: Path) -> None:
        """The index is a derived view. Three skills used to hand-copy a status
        into it that the exchange file already carried."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "open-one", status="open")
        write_exchange(tmp_path, "answered-one", status="answered")
        write_exchange(tmp_path, "closed-one", status="closed")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        index = self._index(tmp_path)
        assert "## Open (1)" in index
        assert "## Answered (1)" in index
        assert "## Closed (1)" in index
        # Open first — it is the only group anyone owes anything on.
        assert index.index("## Open") < index.index("## Answered") < index.index("## Closed")

    def test_gist_comes_from_the_question_heading(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal",
                       body="# Question\nWhat is the drift at 85 C?\n\n# Response\n_(pending)_\n")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "What is the drift at 85 C?" in self._index(tmp_path)

    def test_gist_falls_back_when_the_heading_drifts(self, tmp_path: Path) -> None:
        """The heading is a contract with the `/exchange` templates that nothing
        mechanical holds. If it drifts, the index degrades to a worse gist —
        never to a blank line."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal",
                       body="## Ask\nWhat is the drift at 85 C?\n")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "What is the drift at 85 C?" in self._index(tmp_path)

    def test_placeholder_response_is_not_used_as_a_gist(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal",
                       body="# Question\n\n# Response\n_(filled in by responder)_\n")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "_(filled in by responder)_" not in self._index(tmp_path)

    def test_open_brief_names_who_still_owes_a_disposition(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "drift", kind="brief", from_area="research",
                       to_area="engineering", overrides={"open_for": ["firmware-engineer"]})
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "_awaiting:_ firmware-engineer" in self._index(tmp_path)

    def test_regeneration_is_idempotent(self, tmp_path: Path) -> None:
        """Rule 15 masks the `_Last regenerated:_ stamp when comparing, so a
        no-op run must not dirty the tree — `/check` before a commit would
        otherwise produce a diff nobody made."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        index_path = tmp_path / "exchanges" / "engineering--research" / "index.md"
        before = index_path.stat().st_mtime_ns
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert index_path.stat().st_mtime_ns == before

    def test_hand_edits_are_overwritten(self, tmp_path: Path) -> None:
        """The category is `L`: the file is regenerated, so a hand edit is
        replaced rather than flagged. This is the behaviour change downstream
        projects are warned about in UPGRADING."""
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal")
        index_path = tmp_path / "exchanges" / "engineering--research" / "index.md"
        index_path.write_text("# my notes\n")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "my notes" not in index_path.read_text()

    def test_no_exchanges_directory_writes_nothing(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        assert rule_15_index.check(tmp_path, DEFAULT_CONFIG) == []
        assert not (tmp_path / "exchanges").exists()

    def test_each_pair_directory_gets_its_own_index(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_exchange(tmp_path, "thermal", to_area="research")
        write_exchange(tmp_path, "optics-q", to_area="research/optics")
        rule_15_index.check(tmp_path, DEFAULT_CONFIG)
        assert "ex-2026-05-08-thermal" in self._index(tmp_path, "engineering--research")
        assert "ex-2026-05-08-optics-q" in self._index(tmp_path, "engineering--research-optics")
