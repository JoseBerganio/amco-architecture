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

import logging
import sqlite3
from pathlib import Path

import pytest

import amco.storage.schema as schema
from amco.storage import SchemaError, add_memory, connect, list_memories
from amco.storage import db as db_module
from amco.storage.backup import backup_path
from amco.storage.schema import Migration

BASE_COLUMNS = {"id", "content", "category", "source", "created_at"}


def _legacy_database(path: Path) -> None:
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


def _backups(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.bak-*"))


def _add_extra_column(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE memories ADD COLUMN extra TEXT")


def _half_done_then_fail(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE memories ADD COLUMN extra TEXT")
    raise sqlite3.OperationalError("boom")


# --- Naming ---------------------------------------------------------------------


def test_backup_path_is_plain_first_then_timestamped(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    first = backup_path(db, 0)
    assert first.name == "t.sqlite3.bak-v0"
    first.write_bytes(b"x")

    second = backup_path(db, 0)
    assert second != first
    assert second.name.startswith("t.sqlite3.bak-v0-")
    second.write_bytes(b"y")

    third = backup_path(db, 0)
    assert third not in (first, second)
    assert not third.exists()


# --- When a backup is made ------------------------------------------------------


def test_unversioned_database_is_backed_up_before_it_migrates(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    _legacy_database(db)

    list_memories(db_path=db)

    backup = tmp_path / "legacy.sqlite3.bak-v0"
    assert backup.exists()
    assert _user_version(backup) == 0
    assert _columns(backup) == BASE_COLUMNS
    assert _raw(backup, "SELECT content FROM memories") == [("old memory",)]
    assert _user_version(db) == schema.SCHEMA_VERSION


def test_fresh_database_gets_no_backup(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    connect(db).close()
    assert _backups(tmp_path) == []


def test_reopening_an_up_to_date_database_makes_no_backup(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    connect(db).close()
    connect(db).close()
    connect(db).close()
    assert _backups(tmp_path) == []


def test_newer_database_is_refused_without_a_backup(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("precious", db_path=db)
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {schema.SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()

    with pytest.raises(SchemaError):
        connect(db)

    assert _backups(tmp_path) == []


def test_each_real_migration_gets_its_own_backup(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("original", db_path=db)
    monkeypatch.setattr(
        schema, "MIGRATIONS", [*schema.MIGRATIONS, Migration(2, "add extra", _add_extra_column)]
    )

    connect(db).close()

    backup = tmp_path / "t.sqlite3.bak-v1"
    assert backup.exists()
    assert _user_version(backup) == 1
    assert "extra" not in _columns(backup)
    assert _user_version(db) == 2


# --- Safety of the backup itself ------------------------------------------------


def test_an_existing_backup_is_never_overwritten(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    _legacy_database(db)
    old_backup = tmp_path / "legacy.sqlite3.bak-v0"
    old_backup.write_bytes(b"keep me")

    list_memories(db_path=db)

    assert old_backup.read_bytes() == b"keep me"
    others = [p for p in _backups(tmp_path) if p != old_backup]
    assert len(others) == 1
    assert _raw(others[0], "SELECT content FROM memories") == [("old memory",)]


def test_if_the_backup_fails_the_upgrade_is_not_attempted(tmp_path: Path, monkeypatch):
    db = tmp_path / "legacy.sqlite3"
    _legacy_database(db)

    def disk_full(conn, path, version):
        raise OSError("disk full")

    monkeypatch.setattr(db_module, "backup_database", disk_full)

    with pytest.raises(SchemaError, match="back up"):
        connect(db)

    assert _user_version(db) == 0
    assert _columns(db) == BASE_COLUMNS
    assert _raw(db, "SELECT content FROM memories") == [("old memory",)]


def test_a_failed_migration_still_leaves_its_backup(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("original", db_path=db)
    monkeypatch.setattr(
        schema, "MIGRATIONS", [*schema.MIGRATIONS, Migration(2, "broken", _half_done_then_fail)]
    )

    with pytest.raises(SchemaError, match="Migration 2"):
        connect(db)

    backup = tmp_path / "t.sqlite3.bak-v1"
    assert _raw(backup, "SELECT content FROM memories") == [("original",)]
    assert _user_version(db) == 1


def test_the_backup_is_announced(tmp_path: Path, caplog):
    db = tmp_path / "legacy.sqlite3"
    _legacy_database(db)

    with caplog.at_level(logging.WARNING, logger="amco.storage.backup"):
        list_memories(db_path=db)

    assert "legacy.sqlite3.bak-v0" in caplog.text