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

from pathlib import Path

import pytest

from amco.storage import add_memory, delete_memory, list_memories, search_memories, get_memory, update_memory

import sqlite3



def test_add_and_list_memory(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    memory_id = add_memory("AMCO uses SQLite", db_path=db)
    records = list_memories(db_path=db)
    assert len(records) == 1
    assert records[0]["id"] == memory_id
    assert records[0]["content"] == "AMCO uses SQLite"


def test_search_returns_matching_memory(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    add_memory("Project uses Python and SQLite", db_path=db)
    add_memory("The garden needs watering", db_path=db)
    results = search_memories("SQLite project", db_path=db)
    assert len(results) == 1
    assert "SQLite" in results[0]["content"]


def test_delete_memory(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    memory_id = add_memory("temporary note", db_path=db)
    assert delete_memory(memory_id, db_path=db) is True
    assert list_memories(db_path=db) == []
    assert delete_memory(memory_id, db_path=db) is False


def test_empty_memory_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        add_memory("   ", db_path=tmp_path / "test.sqlite3")

def test_new_memory_has_type_and_timestamps(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    memory_id = add_memory("Use SQLite", memory_type="long_term", db_path=db)
    item = get_memory(memory_id, db_path=db)
    assert item["memory_type"] == "long_term"
    assert item["updated_at"] is not None


def test_invalid_type_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        add_memory("x", memory_type="working", db_path=tmp_path / "test.sqlite3")


def test_get_missing_memory_returns_none(tmp_path: Path):
    assert get_memory(999, db_path=tmp_path / "test.sqlite3") is None


def test_update_memory_changes_fields(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    memory_id = add_memory("old text", category="notes", db_path=db)
    assert update_memory(memory_id, content="new text", memory_type="long_term", db_path=db)
    item = get_memory(memory_id, db_path=db)
    assert item["content"] == "new text"
    assert item["memory_type"] == "long_term"
    assert item["category"] == "notes"  # untouched


def test_update_missing_memory_returns_false(tmp_path: Path):
    assert update_memory(42, content="x", db_path=tmp_path / "test.sqlite3") is False


def test_update_requires_a_field_and_valid_content(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    memory_id = add_memory("keep me", db_path=db)
    with pytest.raises(ValueError):
        update_memory(memory_id, db_path=db)
    with pytest.raises(ValueError):
        update_memory(memory_id, content="   ", db_path=db)
    assert get_memory(memory_id, db_path=db)["content"] == "keep me"


def test_list_filters_by_type(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    add_memory("a", memory_type="persistent", db_path=db)
    add_memory("b", memory_type="long_term", db_path=db)
    results = list_memories(db_path=db, memory_type="long_term")
    assert [m["content"] for m in results] == ["b"]


def test_sprint1_database_is_migrated(tmp_path: Path):
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

    records = list_memories(db_path=db)
    assert records[0]["content"] == "old memory"
    assert records[0]["memory_type"] == "persistent"
    assert records[0]["updated_at"] == records[0]["created_at"]