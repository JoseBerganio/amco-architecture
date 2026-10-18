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

import sqlite3
from pathlib import Path

import pytest

from amco.storage import (
    add_memory,
    check_duplicates,
    delete_memory,
    get_memory,
    list_memories,
    memory_status,
    record_usage,
    restore_memory,
    search_memories,
    supersede_memory,
    update_memory,
)


def test_exact_duplicate_ignores_case_spacing_and_punctuation(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    first = add_memory("Project uses SQLite", db_path=db)
    exact, _ = check_duplicates("  project   USES sqlite. ", db_path=db)
    assert exact["id"] == first


def test_similar_memories_are_reported_but_unrelated_ones_are_not(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("The API timeout for requests is 30 seconds", db_path=db)
    add_memory("The garden needs watering on Sundays", db_path=db)
    exact, similar = check_duplicates("The API timeout for requests is 60 seconds", db_path=db)
    assert exact is None
    assert len(similar) == 1
    assert similar[0]["similarity"] >= 0.6


def test_supersede_hides_old_memory_but_keeps_it(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    old = add_memory("Storage uses JSON files", db_path=db)
    new = add_memory("Storage uses SQLite", db_path=db)
    assert supersede_memory(old, new, db_path=db) is True

    assert [m["id"] for m in search_memories("storage", db_path=db)] == [new]
    assert [m["id"] for m in list_memories(db_path=db)] == [new]
    assert {m["id"] for m in list_memories(db_path=db, include_inactive=True)} == {old, new}
    assert memory_status(get_memory(old, db_path=db)) == "superseded"

    assert restore_memory(old, db_path=db) is True
    assert len(search_memories("storage", db_path=db)) == 2


def test_add_with_supersedes_is_atomic(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    old = add_memory("Storage uses JSON files", db_path=db)
    new = add_memory("Storage uses SQLite", db_path=db, supersedes=old)
    assert get_memory(old, db_path=db)["superseded_by"] == new

    with pytest.raises(ValueError):
        add_memory("Should not be saved", db_path=db, supersedes=999)
    assert len(list_memories(db_path=db, include_inactive=True)) == 2


def test_supersede_rejects_invalid_requests(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    a = add_memory("a note", db_path=db)
    b = add_memory("b note", db_path=db)
    c = add_memory("c note", db_path=db)
    with pytest.raises(ValueError):
        supersede_memory(a, a, db_path=db)
    supersede_memory(a, b, db_path=db)
    with pytest.raises(ValueError):
        supersede_memory(a, c, db_path=db)      # already superseded
    with pytest.raises(ValueError):
        supersede_memory(c, a, db_path=db)      # replacement is itself superseded
    with pytest.raises(ValueError):
        supersede_memory(c, 999, db_path=db)    # replacement does not exist
    assert supersede_memory(999, b, db_path=db) is False


def test_deleting_a_replacement_revives_what_it_replaced(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    old = add_memory("old", db_path=db)
    new = add_memory("new", db_path=db)
    supersede_memory(old, new, db_path=db)
    delete_memory(new, db_path=db)
    assert get_memory(old, db_path=db)["superseded_by"] is None


def test_deleting_a_middle_link_keeps_the_chain_hidden(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    a = add_memory("first version", db_path=db)
    b = add_memory("second version", db_path=db)
    c = add_memory("third version", db_path=db)
    supersede_memory(a, b, db_path=db)
    supersede_memory(b, c, db_path=db)
    delete_memory(b, db_path=db)
    assert get_memory(a, db_path=db)["superseded_by"] == c


def test_expired_memory_is_hidden_but_kept(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("Sprint demo is on Friday", db_path=db, expires_at="2000-01-01")
    assert search_memories("demo", db_path=db) == []
    assert list_memories(db_path=db) == []
    assert memory_status(get_memory(memory_id, db_path=db)) == "expired"


def test_future_expiry_stays_active(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("Sprint demo is on Friday", db_path=db, expires_at="2999-12-31")
    assert len(search_memories("demo", db_path=db)) == 1


def test_expiry_is_validated_and_can_be_changed_or_cleared(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    with pytest.raises(ValueError):
        add_memory("x", db_path=db, expires_at="next week")
    memory_id = add_memory("a note", db_path=db)
    update_memory(memory_id, expires_at="2999-12-31", db_path=db)
    assert get_memory(memory_id, db_path=db)["expires_at"] == "2999-12-31"
    update_memory(memory_id, expires_at="none", db_path=db)
    assert get_memory(memory_id, db_path=db)["expires_at"] is None


def test_record_usage_stamps_last_used(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("a note", db_path=db)
    assert get_memory(memory_id, db_path=db)["last_used_at"] is None
    record_usage([memory_id], db_path=db)
    assert get_memory(memory_id, db_path=db)["last_used_at"] is not None


def test_older_database_gains_sprint5_columns(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO memories(content) VALUES ('old memory')")
    conn.commit()
    conn.close()
    record = list_memories(db_path=db)[0]
    assert record["superseded_by"] is None
    assert record["expires_at"] is None
    assert record["last_used_at"] is None