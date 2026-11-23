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

import amco.storage.schema as schema
from amco.storage import (
    VALID_KINDS,
    VALID_SOURCES,
    add_memory,
    get_memory,
    list_memories,
    search_memories,
    update_memory,
)

NEW_COLUMNS = {"kind", "source_session", "period_start", "period_end"}


def _raw(path: Path, sql: str) -> list:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _columns(path: Path) -> set[str]:
    return {row[1] for row in _raw(path, "PRAGMA table_info(memories)")}


def _database_with_v1_columns(path: Path, user_version: int) -> None:
    """A 0.5-style database: every version 1 column, none of the version 2 ones."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for name, definition in schema._V1_COLUMNS:
        conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")
    conn.execute("INSERT INTO memories(content, updated_at) VALUES ('kept', CURRENT_TIMESTAMP)")
    conn.execute(f"PRAGMA user_version = {user_version}")
    conn.commit()
    conn.close()


# --- Constants -------------------------------------------------------------------


def test_valid_kinds_and_sources():
    assert VALID_KINDS == ("fact", "summary", "record")
    assert VALID_SOURCES == ("user", "chat", "summary")


# --- Defaults and the tier rule (K6, K8) -------------------------------------------


def test_a_plain_memory_is_a_persistent_user_fact(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    item = get_memory(add_memory("Use SQLite", db_path=db), db_path=db)
    assert (item["kind"], item["memory_type"], item["source"]) == ("fact", "persistent", "user")
    assert (item["source_session"], item["period_start"], item["period_end"]) == (None, None, None)


@pytest.mark.parametrize("kind", ["summary", "record"])
def test_summaries_and_records_default_to_long_term(tmp_path: Path, kind: str):
    db = tmp_path / "t.sqlite3"
    item = get_memory(add_memory("Session recap", kind=kind, db_path=db), db_path=db)
    assert item["kind"] == kind and item["memory_type"] == "long_term"


def test_an_explicit_type_always_wins(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    promoted = get_memory(add_memory("Recap", kind="summary", memory_type="persistent", db_path=db), db_path=db)
    archived = get_memory(add_memory("A fact", kind="fact", memory_type="long_term", db_path=db), db_path=db)
    assert promoted["memory_type"] == "persistent"
    assert archived["memory_type"] == "long_term"


def test_kind_and_source_ignore_case_and_spaces(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    item = get_memory(add_memory("x", kind=" Summary ", source="CHAT", db_path=db), db_path=db)
    assert (item["kind"], item["source"]) == ("summary", "chat")


def test_invalid_kind_source_and_type_are_rejected(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    with pytest.raises(ValueError, match="Memory kind"):
        add_memory("x", kind="diary", db_path=db)
    with pytest.raises(ValueError, match="Memory source"):
        add_memory("x", source="robot", db_path=db)
    with pytest.raises(ValueError, match="Memory type"):
        add_memory("x", memory_type="working", db_path=db)
    assert list_memories(db_path=db) == []


# --- Session and period ------------------------------------------------------------


def test_session_and_period_are_stored(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory(
        "Recap", kind="summary", source="chat", source_session="  a1b2c3  ",
        period_start="2026-11-19 09:00:00", period_end="2026-11-19 10:30:00", db_path=db,
    )
    item = get_memory(memory_id, db_path=db)
    assert item["source_session"] == "a1b2c3"
    assert (item["period_start"], item["period_end"]) == ("2026-11-19 09:00:00", "2026-11-19 10:30:00")
    assert item["source"] == "chat"


def test_blank_session_and_period_count_as_not_given(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    item = get_memory(
        add_memory("x", source_session="  ", period_start=" ", period_end="", db_path=db), db_path=db
    )
    assert (item["source_session"], item["period_start"], item["period_end"]) == (None, None, None)


def test_dates_are_accepted_and_one_bound_alone_is_fine(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    both = get_memory(add_memory("a", period_start="2026-11-01", period_end="2026-11-07", db_path=db), db_path=db)
    only_start = get_memory(add_memory("b", period_start="2026-11-01", db_path=db), db_path=db)
    assert (both["period_start"], both["period_end"]) == ("2026-11-01", "2026-11-07")
    assert (only_start["period_start"], only_start["period_end"]) == ("2026-11-01", None)


def test_a_date_only_end_runs_to_the_end_of_that_day(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("one day", period_start="2026-11-19", period_end="2026-11-19", db_path=db)
    add_memory("late start", period_start="2026-11-19 18:00:00", period_end="2026-11-19", db_path=db)
    assert len(list_memories(db_path=db)) == 2


def test_bad_periods_are_rejected_and_nothing_is_saved(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    with pytest.raises(ValueError, match="Period start must be"):
        add_memory("x", period_start="yesterday", db_path=db)
    with pytest.raises(ValueError, match="Period end must be"):
        add_memory("x", period_end="2026-13-45", db_path=db)
    with pytest.raises(ValueError, match="cannot be after"):
        add_memory("x", period_start="2026-11-20", period_end="2026-11-19", db_path=db)
    with pytest.raises(ValueError, match="cannot be after"):
        add_memory("x", period_start="2026-11-19 10:00:00", period_end="2026-11-19 09:00:00", db_path=db)
    assert list_memories(db_path=db) == []


# --- update_memory -----------------------------------------------------------------


def test_update_changes_the_kind_but_never_the_tier(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("a note", db_path=db)
    assert update_memory(memory_id, kind="record", db_path=db) is True
    item = get_memory(memory_id, db_path=db)
    assert item["kind"] == "record" and item["memory_type"] == "persistent"


def test_update_rejects_an_invalid_kind_and_keeps_the_old_one(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("a note", db_path=db)
    with pytest.raises(ValueError, match="Memory kind"):
        update_memory(memory_id, kind="diary", db_path=db)
    assert get_memory(memory_id, db_path=db)["kind"] == "fact"


def test_update_with_nothing_still_raises(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("a note", db_path=db)
    with pytest.raises(ValueError, match="Nothing to update"):
        update_memory(memory_id, db_path=db)


# --- Reading back --------------------------------------------------------------------


def test_list_and_search_results_carry_the_new_fields(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("Storage recap for the week", kind="summary", source_session="s1", db_path=db)
    listed = list_memories(db_path=db)[0]
    found = search_memories("storage", db_path=db)[0]
    for record in (listed, found):
        assert record["kind"] == "summary" and record["source_session"] == "s1"
        assert NEW_COLUMNS <= set(record)


# --- Migration 1 to 2 ------------------------------------------------------------------


def test_a_version_1_database_gains_the_columns_and_keeps_its_data(tmp_path: Path):
    db = tmp_path / "v1.sqlite3"
    _database_with_v1_columns(db, user_version=1)

    record = list_memories(db_path=db)[0]

    assert record["content"] == "kept"
    assert (record["kind"], record["source_session"]) == ("fact", None)
    assert (record["period_start"], record["period_end"]) == (None, None)
    assert _raw(db, "PRAGMA user_version") == [(schema.SCHEMA_VERSION,)]
    backup = tmp_path / "v1.sqlite3.bak-v1"
    assert backup.exists()
    assert not NEW_COLUMNS & _columns(backup)


def test_an_unversioned_05_database_gets_one_backup_for_both_migrations(tmp_path: Path):
    db = tmp_path / "v0.sqlite3"
    _database_with_v1_columns(db, user_version=0)

    assert list_memories(db_path=db)[0]["kind"] == "fact"

    assert _raw(db, "PRAGMA user_version") == [(schema.SCHEMA_VERSION,)]
    assert sorted(p.name for p in tmp_path.glob("*.bak-*")) == ["v0.sqlite3.bak-v0"]


def test_a_fresh_database_has_the_new_columns_and_no_backup(tmp_path: Path):
    db = tmp_path / "fresh.sqlite3"
    add_memory("x", db_path=db)
    assert NEW_COLUMNS <= _columns(db)
    assert list(tmp_path.glob("*.bak-*")) == []
    
    
def test_list_filters_by_kind_and_combines_with_type(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("a fact", db_path=db)
    summary = add_memory("a recap", kind="summary", db_path=db)
    record = add_memory("a log", kind="record", memory_type="persistent", db_path=db)

    assert [m["id"] for m in list_memories(db_path=db, kind="summary")] == [summary]
    assert [m["id"] for m in list_memories(db_path=db, kind="record", memory_type="persistent")] == [record]
    assert list_memories(db_path=db, kind="record", memory_type="long_term") == []
    with pytest.raises(ValueError, match="Memory kind"):
        list_memories(db_path=db, kind="diary")