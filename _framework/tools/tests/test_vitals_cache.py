"""
Tests for _framework/tools/vitals_cache.py and kb_vitals.refresh_cache
"""

from __future__ import annotations

from pathlib import Path

import kb_vitals as kv
import vitals_cache as vc
from lint_helpers import make_minimal_repo

_CONFIG = {"lint": {}, "capabilities": {"multi_area": True}, "kb_vitals": {}}


def _area(repo: Path, area: str = "areas/research", role: str = "researcher") -> Path:
    d = repo / area
    (d / "roles" / role).mkdir(parents=True, exist_ok=True)
    (d / "kb" / "findings").mkdir(parents=True, exist_ok=True)
    (d / "brief.md").write_text("# brief\n")  # iter_areas keys on brief.md
    return d


class TestReadWrite:
    def test_read_absent_is_empty(self, tmp_path: Path) -> None:
        assert vc.read(tmp_path) == {}

    def test_read_malformed_is_empty(self, tmp_path: Path) -> None:
        vc.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        vc.path(tmp_path).write_text("{not json")
        assert vc.read(tmp_path) == {}

    def test_round_trip_creates_dirs(self, tmp_path: Path) -> None:
        vc.write(tmp_path, {"commons_awaiting_review": 3})
        assert vc.read(tmp_path)["commons_awaiting_review"] == 3

    def test_write_leaves_no_temp_file(self, tmp_path: Path) -> None:
        """Written through a temp file + os.replace so a concurrent reader never
        sees a half-written cache."""
        vc.write(tmp_path, {"commons_awaiting_review": 1})
        assert list(vc.path(tmp_path).parent.glob("*.tmp")) == []

    def test_write_is_last_writer_wins(self, tmp_path: Path) -> None:
        vc.write(tmp_path, {"commons_awaiting_review": 1})
        vc.write(tmp_path, {"commons_awaiting_review": 9})
        assert vc.read(tmp_path)["commons_awaiting_review"] == 9


class TestAccessors:
    def test_defaults_when_keys_absent(self, tmp_path: Path) -> None:
        assert vc.commons_awaiting_review({}) == 0
        assert vc.exchange_counts({}, "areas/research") == 0
        assert vc.preload_newest_update({}, "areas/research", "researcher") is None

    def test_ignores_wrong_types(self) -> None:
        """A hand-mangled cache must read as 'unknown', never as a wrong count."""
        cache = {"commons_awaiting_review": "two", "areas": "nope"}
        assert vc.commons_awaiting_review(cache) == 0
        assert vc.exchange_counts(cache, "areas/research") == 0
        assert vc.preload_newest_update(cache, "areas/research", "r") is None

    def test_reads_per_area_and_per_role(self) -> None:
        cache = {"areas": {
            "areas/research": {
                "exchanges_to_answer": 2, "exchanges_to_close": 1,
                "roles": {"researcher": {"preload_newest_update": "2026-08-20"}},
            },
            "areas/engineering": {"exchanges_to_answer": 0, "exchanges_to_close": 0},
        }}
        assert vc.exchange_counts(cache, "areas/research") == 3
        assert vc.exchange_counts(cache, "areas/engineering") == 0
        assert vc.preload_newest_update(cache, "areas/research", "researcher") == "2026-08-20"
        # A role that isn't in the snapshot is unknown, not zero-dated.
        assert vc.preload_newest_update(cache, "areas/research", "other") is None


class TestRefreshCache:
    def test_counts_commons_awaiting_review(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        cdir = tmp_path / "commons" / "kb" / "findings"
        cdir.mkdir(parents=True)
        (cdir / "f-a.md").write_text("---\nid: f-a\nhuman_reviewed: false\n---\nBody.\n")
        (cdir / "f-b.md").write_text("---\nid: f-b\nhuman_reviewed: true\n---\nBody.\n")
        snapshot = kv.refresh_cache(tmp_path, _CONFIG)
        assert snapshot["commons_awaiting_review"] == 1
        assert vc.read(tmp_path)["commons_awaiting_review"] == 1

    def test_counts_exchanges_per_area(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _area(tmp_path)
        ex = tmp_path / "exchanges" / "research--engineering"
        ex.mkdir(parents=True)
        (ex / "q-1.md").write_text(
            "---\nstatus: open\nfrom_area: areas/engineering\nto_area: areas/research\n---\n")
        (ex / "q-2.md").write_text(
            "---\nstatus: answered\nfrom_area: areas/research\nto_area: areas/engineering\n---\n")
        entry = kv.refresh_cache(tmp_path, _CONFIG)["areas"]["areas/research"]
        assert entry["exchanges_to_answer"] == 1
        assert entry["exchanges_to_close"] == 1

    def test_exchanges_omitted_when_capability_off(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        _area(tmp_path)
        config = {"lint": {}, "capabilities": {"multi_area": False}, "kb_vitals": {}}
        entry = kv.refresh_cache(tmp_path, config)["areas"]["areas/research"]
        assert "exchanges_to_answer" not in entry

    def test_records_newest_preload_update_per_role(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        area = _area(tmp_path)
        pages = area / "kb" / "findings"
        (pages / "f-x.md").write_text("---\nid: f-x\nupdated: 2026-05-08\n---\nBody.\n")
        (pages / "f-y.md").write_text("---\nid: f-y\nupdated: 2026-08-20\n---\nBody.\n")
        (area / "roles" / "researcher" / "role.md").write_text(
            "# researcher\n\n## Preload context (full)\n\n"
            "1. /areas/research/kb/findings/f-x.md\n"
            "2. /areas/research/kb/findings/f-y.md\n"
        )
        snapshot = kv.refresh_cache(tmp_path, _CONFIG)
        roles = snapshot["areas"]["areas/research"]["roles"]
        assert roles["researcher"]["preload_newest_update"] == "2026-08-20"

    def test_role_without_dated_preload_is_omitted(self, tmp_path: Path) -> None:
        """No date is 'unknown', and the reader must not treat it as a date."""
        make_minimal_repo(tmp_path)
        area = _area(tmp_path)
        (area / "roles" / "researcher" / "role.md").write_text(
            "# researcher\n\n## Preload context (full)\n\n_None yet._\n")
        entry = kv.refresh_cache(tmp_path, _CONFIG)["areas"]["areas/research"]
        assert "roles" not in entry

    def test_empty_repo_is_not_an_error(self, tmp_path: Path) -> None:
        make_minimal_repo(tmp_path)
        snapshot = kv.refresh_cache(tmp_path, _CONFIG)
        assert snapshot["commons_awaiting_review"] == 0
        assert snapshot["areas"] == {}
