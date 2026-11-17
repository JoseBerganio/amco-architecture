# SPDX-License-Identifier: GPL-2.0-or-later
#
# AMCO — Adaptive Memory Controller
# Copyright (C) 2026  Jose Berganio
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see
# <https://www.gnu.org/licenses/>.

from datetime import datetime, timezone
from pathlib import Path

import pytest

from amco.evaluation import build_database, parse_fixtures
from amco.storage import get_memory, list_memories

NOW = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)


def _fixtures():
    return parse_fixtures({
        "name": "build",
        "memories": [
            {"key": "a", "content": "alpha fact", "category": "tech", "memory_type": "long_term",
             "confidence": 0.7, "age_days": 10, "use_count": 4},
            {"key": "old", "content": "old fact", "age_days": 30},
            {"key": "new", "content": "new fact", "age_days": 1, "supersedes": "old"},
            {"key": "gone", "content": "gone fact", "expires_in_days": -3},
            {"key": "soon", "content": "soon fact", "expires_in_days": 5},
        ],
        "queries": [{"id": "q", "query": "new fact", "expect": ["new"], "tags": ["exact"]}],
    })


def test_ids_follow_definition_order(tmp_path: Path):
    ids = build_database(_fixtures(), tmp_path / "e.sqlite3")
    assert list(ids) == ["a", "old", "new", "gone", "soon"]
    assert list(ids.values()) == sorted(ids.values())


def test_stored_fields_stamps_and_use_count(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    ids = build_database(_fixtures(), db, now=NOW)
    a = get_memory(ids["a"], db_path=db)
    assert a["created_at"] == a["updated_at"] == "2026-11-02 12:00:00"
    assert (a["use_count"], a["confidence"]) == (4, 0.7)
    assert (a["memory_type"], a["category"]) == ("long_term", "tech")
    assert get_memory(ids["old"], db_path=db)["created_at"] == "2026-10-13 12:00:00"


def test_expiry_dates_are_relative_to_the_build_date(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    ids = build_database(_fixtures(), db, now=NOW)
    assert get_memory(ids["gone"], db_path=db)["expires_at"] == "2026-11-09"
    assert get_memory(ids["soon"], db_path=db)["expires_at"] == "2026-11-17"
    assert get_memory(ids["a"], db_path=db)["expires_at"] is None


def test_a_naive_now_is_treated_as_utc(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    ids = build_database(_fixtures(), db, now=datetime(2026, 11, 12, 12, 0, 0))
    assert get_memory(ids["a"], db_path=db)["updated_at"] == "2026-11-02 12:00:00"


def test_supersession_and_expiry_hide_memories_but_keep_them(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    ids = build_database(_fixtures(), db)  # real clock, so "gone" is expired and "soon" is not
    assert get_memory(ids["old"], db_path=db)["superseded_by"] == ids["new"]
    visible = {m["id"] for m in list_memories(db_path=db)}
    assert visible == {ids["a"], ids["new"], ids["soon"]}
    assert len(list_memories(db_path=db, include_inactive=True)) == 5


def test_a_database_that_already_has_data_is_refused(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    build_database(_fixtures(), db)
    with pytest.raises(ValueError, match="already contains data"):
        build_database(_fixtures(), db)