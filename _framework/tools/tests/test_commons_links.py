"""
Tests for the commons twin-map and link-rewrite helpers in common.py
(Phase 1 of commons drift & link management).
"""

from __future__ import annotations

from pathlib import Path

from common import (
    build_twin_resolver,
    commons_twin_map,
    rewrite_links_to_twins,
)

from lint_helpers import make_minimal_repo, write_kb_page


class TestCommonsTwinMap:
    def test_maps_source_to_commons_twin(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "commons", "finding", "shot-noise",
            frontmatter_overrides={
                "id": "f-commons-shot-noise",
                "promoted_from_page": "f-2026-05-shot-noise",
            },
        )
        assert commons_twin_map(tmp_path) == {
            "f-2026-05-shot-noise": "f-commons-shot-noise"
        }

    def test_multi_source_synthesis(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "commons", "finding", "synth",
            frontmatter_overrides={
                "id": "f-commons-synth",
                "promoted_from_page": ["f-2026-05-a", "f-2026-05-b"],
            },
        )
        assert commons_twin_map(tmp_path) == {
            "f-2026-05-a": "f-commons-synth",
            "f-2026-05-b": "f-commons-synth",
        }

    def test_wikilink_valued_source(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(
            tmp_path, "commons", "finding", "wl",
            frontmatter_overrides={
                "id": "f-commons-wl",
                "promoted_from_page": "[[findings/f-2026-05-wl]]",
            },
        )
        assert commons_twin_map(tmp_path) == {"f-2026-05-wl": "f-commons-wl"}

    def test_empty_when_no_commons(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        assert commons_twin_map(tmp_path) == {}


def _resolve(mapping):
    """Fake resolve_twin: bare/prefixed/path target -> twin id via an id map."""
    def resolve_twin(target: str):
        t = target.split(":", 1)[-1].rsplit("/", 1)[-1]
        return mapping.get(t)
    return resolve_twin


class TestRewriteLinksToTwins:
    def test_rewrites_when_twin_exists(self) -> None:
        body = "Builds on [[c-2026-05-foo]] and stands alone.\n"
        new, changes = rewrite_links_to_twins(body, _resolve({"c-2026-05-foo": "c-commons-foo"}))
        assert "[[c-commons-foo]]" in new
        assert changes == [("c-2026-05-foo", "c-commons-foo")]

    def test_leaves_link_without_twin(self) -> None:
        body = "Cites [[s-2026-05-src]] for provenance.\n"
        new, changes = rewrite_links_to_twins(body, _resolve({}))
        assert new == body
        assert changes == []

    def test_preserves_alias(self) -> None:
        body = "See [[research:concepts/c-2026-05-foo|the workspace idea]].\n"
        new, _ = rewrite_links_to_twins(body, _resolve({"c-2026-05-foo": "c-commons-foo"}))
        assert "[[c-commons-foo|the workspace idea]]" in new

    def test_rewrites_prefixed_target_to_bare_twin(self) -> None:
        body = "Per [[research:findings/f-2026-05-foo]].\n"
        new, _ = rewrite_links_to_twins(body, _resolve({"f-2026-05-foo": "f-commons-foo"}))
        assert "[[f-commons-foo]]" in new
        assert "research:" not in new

    def test_skips_code_fences(self) -> None:
        body = "```\n[[c-2026-05-foo]]\n```\nOutside [[c-2026-05-foo]].\n"
        new, changes = rewrite_links_to_twins(body, _resolve({"c-2026-05-foo": "c-commons-foo"}))
        assert new.count("[[c-2026-05-foo]]") == 1   # fenced one untouched
        assert "[[c-commons-foo]]" in new
        assert len(changes) == 1

    def test_build_twin_resolver_integration(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        write_kb_page(tmp_path, "areas/research", "concept", "foo")  # id c-2026-05-foo
        commons_dir = tmp_path / "commons" / "kb" / "concepts"
        commons_dir.mkdir(parents=True, exist_ok=True)
        (commons_dir / "c-commons-foo.md").write_text(
            "---\nid: c-commons-foo\ntitle: Foo\ntype: concept\nstatus: supported\n"
            "area: commons\ncreated: 2026-05-08\nupdated: 2026-05-08\n"
            "summary: Foo.\npromoted_from_page: c-2026-05-foo\n---\n\nBody.\n"
        )
        resolve = build_twin_resolver(tmp_path)
        new, changes = rewrite_links_to_twins("Builds on [[c-2026-05-foo]].\n", resolve)
        assert "[[c-commons-foo]]" in new
        assert changes == [("c-2026-05-foo", "c-commons-foo")]
