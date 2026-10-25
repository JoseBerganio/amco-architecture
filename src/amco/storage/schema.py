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

"""Schema versioning and migrations.

The schema version lives in SQLite's `PRAGMA user_version`, a field in the
database file header. It is not a table, so it never appears in sqlite_master
and does not change the schema fingerprint.

    0  unversioned: every database made by AMCO 0.1 to 0.5
    1  the 0.5 schema (migration 1 upgrades any unversioned database to it)

Rules for adding a migration:
  * Append a new Migration with the next number. Never edit an old one.
  * Do not use executescript(): it commits implicitly and would break the
    all-or-nothing guarantee. Use conn.execute() only.
  * Do not commit or roll back inside a migration. migrate() does that.

This module imports only the standard library, so it can sit at the bottom of
the storage layering.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


class SchemaError(Exception):
    """The database schema cannot be used or upgraded.

    Deliberately NOT a RuntimeError: the chat loop treats RuntimeError as a
    model error, and this is a database problem.
    """


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    apply: Callable[[sqlite3.Connection], None]


# --- Migration 1: unversioned -> the 0.5 schema ------------------------------

# The order is part of the contract. ALTER TABLE appends each definition to the
# stored CREATE TABLE text, so changing this order changes the schema
# fingerprint. The text of each definition must stay exactly as written.
_V1_COLUMNS = (
    ("updated_at", "TEXT"),
    ("memory_type", "TEXT NOT NULL DEFAULT 'persistent'"),
    ("confidence", "REAL NOT NULL DEFAULT 1.0"),
    ("use_count", "INTEGER NOT NULL DEFAULT 0"),
    ("superseded_by", "INTEGER"),
    ("superseded_at", "TEXT"),
    ("expires_at", "TEXT"),
    ("last_used_at", "TEXT"),
)


def _migration_1(conn: sqlite3.Connection) -> None:
    """Add every column introduced in Sprints 2, 4 and 5 that is still missing.

    Idempotent on purpose: a 0.5 database is also "unversioned", and already
    has all of these columns.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
    for name, definition in _V1_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")
    conn.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")


MIGRATIONS: list[Migration] = [
    Migration(1, "Bring any 0.1 to 0.5 database to the 0.5 schema", _migration_1),
]

SCHEMA_VERSION = MIGRATIONS[-1].version


# --- Running migrations -------------------------------------------------------


def latest_version() -> int:
    """The newest schema version this AMCO knows. Read at call time (tests patch MIGRATIONS)."""
    return MIGRATIONS[-1].version


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _reject_newer(version: int) -> None:
    latest = latest_version()
    if version > latest:
        raise SchemaError(
            f"This database uses schema version {version}, which is newer than the "
            f"latest version this AMCO understands ({latest}). It was probably created "
            "by a newer AMCO. Upgrade AMCO, or point AMCO_DB_PATH at a different database."
        )


def pending(conn: sqlite3.Connection) -> list[Migration]:
    """Migrations that have not been applied yet. Raises SchemaError for a newer database."""
    version = current_version(conn)
    _reject_newer(version)
    return [m for m in MIGRATIONS if m.version > version]


def _apply(conn: sqlite3.Connection, migration: Migration) -> bool:
    """Apply one migration atomically. Returns False if someone else already did.

    BEGIN IMMEDIATE takes the write lock up front. user_version is re-read
    AFTER the lock is held, so two processes (say a chat session and a CLI
    command) can never both run the same migration. The DDL, the data changes
    and the version bump commit together or not at all.
    """
    try:
        conn.execute("BEGIN IMMEDIATE")
        version = current_version(conn)
        _reject_newer(version)
        if version >= migration.version:
            conn.rollback()
            return False
        migration.apply(conn)
        conn.execute(f"PRAGMA user_version = {int(migration.version)}")
        conn.commit()
        return True
    except sqlite3.Error as exc:
        conn.rollback()
        raise SchemaError(
            f"Migration {migration.version} ({migration.description}) failed and was "
            f"rolled back: {exc}"
        ) from exc
    except BaseException:
        conn.rollback()
        raise


def migrate(
    conn: sqlite3.Connection,
    before: Callable[[int, list[Migration]], None] | None = None,
) -> list[int]:
    """Bring the database up to the latest version. Returns the versions applied.

    `before(old_version, pending)` is called once, only when something is
    pending, and before the first migration runs. If it raises, nothing is
    migrated. connect() uses it to back the database up first.

    An up-to-date database costs one PRAGMA read and takes no write lock.
    """
    to_run = pending(conn)
    if to_run and before is not None:
        # Pending migrations are consecutive, so the old version is one below the first.
        before(to_run[0].version - 1, to_run)
    applied: list[int] = []
    for migration in to_run:
        if _apply(conn, migration):
            applied.append(migration.version)
    return applied