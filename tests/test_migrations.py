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
from amco.storage import SchemaError, add_memory, connect, list_memories
from amco.storage.schema import Migration


def _legacy_database(path: Path) -> None:
    """A Sprint 1 database: five columns, unversioned."""
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
    conn.execute("INSERT INTO memories(content) VALUES ('old memory')")
    conn.commit()
    conn.close()


def _raw(path: Path, sql: str) -> list:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _user_version(path: Path) -> int:
    return _raw(path, "PRAGMA user_version")[0][0]


def _columns(path: Path) -> set[str]:
    return {row[1] for row in _raw(path, "PRAGMA table_info(memories)")}


def _add_extra_column(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE memories ADD COLUMN extra TEXT")


def _half_done_then_fail(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE memories ADD COLUMN extra TEXT")
    conn.execute("UPDATE memories SET content = 'changed'")
    raise sqlite3.OperationalError("boom")


def _bug(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE memories ADD COLUMN extra TEXT")
    raise ValueError("a bug in the migration")


# --- The registry -------------------------------------------------------------


def test_migrations_are_numbered_without_gaps():
    versions = [m.version for m in schema.MIGRATIONS]
    assert versions == list(range(1, len(versions) + 1))
    assert schema.SCHEMA_VERSION == versions[-1]


def test_schema_error_is_not_a_runtime_error():
    assert not issubclass(SchemaError, RuntimeError)


# --- Upgrading real databases ---------------------------------------------------


def test_fresh_database_ends_at_the_latest_version(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    connect(db).close()
    assert _user_version(db) == schema.SCHEMA_VERSION


def test_unversioned_sprint1_database_migrates_with_its_data(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    _legacy_database(db)
    assert _user_version(db) == 0

    records = list_memories(db_path=db)

    assert [r["content"] for r in records] == ["old memory"]
    assert records[0]["memory_type"] == "persistent"
    assert _user_version(db) == schema.SCHEMA_VERSION
    assert {"updated_at", "last_used_at", "superseded_by"} <= _columns(db)


def test_a_current_schema_database_without_a_version_just_gets_stamped(tmp_path: Path):
    """A 0.5 database has every column but user_version 0."""
    db = tmp_path / "t.sqlite3"
    add_memory("kept", db_path=db)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    assert [m["content"] for m in list_memories(db_path=db)] == ["kept"]
    assert _user_version(db) == schema.SCHEMA_VERSION


def test_reopening_applies_nothing(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    connect(db).close()
    conn = connect(db)
    try:
        assert schema.migrate(conn) == []
    finally:
        conn.close()


def test_a_migration_already_applied_elsewhere_is_skipped(tmp_path: Path):
    """The version is re-read after the write lock is taken."""
    db = tmp_path / "t.sqlite3"
    connect(db).close()
    conn = sqlite3.connect(db)
    try:
        assert schema._apply(conn, schema.MIGRATIONS[0]) is False
    finally:
        conn.close()
    assert _user_version(db) == schema.SCHEMA_VERSION


# --- Refusing a newer database ----------------------------------------------------


def test_database_from_a_newer_amco_is_refused_and_left_alone(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("precious", db_path=db)
    newer = schema.SCHEMA_VERSION + 1
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {newer}")
    conn.commit()
    conn.close()

    with pytest.raises(SchemaError, match="newer"):
        connect(db)

    assert _user_version(db) == newer
    assert _raw(db, "SELECT content FROM memories") == [("precious",)]


# --- Applying and rolling back --------------------------------------------------


def test_a_second_migration_is_applied_and_versioned(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("original", db_path=db)
    monkeypatch.setattr(
        schema, "MIGRATIONS", [*schema.MIGRATIONS, Migration(2, "add extra", _add_extra_column)]
    )

    connect(db).close()

    assert _user_version(db) == 2
    assert "extra" in _columns(db)
    assert _raw(db, "SELECT content FROM memories") == [("original",)]


def test_a_failing_migration_rolls_back_schema_data_and_version(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("original", db_path=db)
    monkeypatch.setattr(
        schema, "MIGRATIONS", [*schema.MIGRATIONS, Migration(2, "broken", _half_done_then_fail)]
    )

    with pytest.raises(SchemaError, match="Migration 2"):
        connect(db)

    assert _user_version(db) == 1
    assert "extra" not in _columns(db)
    assert _raw(db, "SELECT content FROM memories") == [("original",)]


def test_a_bug_in_a_migration_rolls_back_and_is_not_disguised(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("original", db_path=db)
    monkeypatch.setattr(
        schema, "MIGRATIONS", [*schema.MIGRATIONS, Migration(2, "buggy", _bug)]
    )

    with pytest.raises(ValueError, match="a bug in the migration"):
        connect(db)

    assert _user_version(db) == 1
    assert "extra" not in _columns(db)