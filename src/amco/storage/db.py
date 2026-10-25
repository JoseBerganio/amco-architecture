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

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..config import database_path
from .schema import migrate

# The newline before the closing parenthesis is part of the schema fingerprint:
# ALTER TABLE inserts new columns after it. Do not reformat this statement.
_BASE_TABLE = """
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        source TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_BASE_TABLE)
        migrate(conn)
        _ensure_fts(conn)
        conn.commit()
    except BaseException:
        conn.close()  # a refused or failed upgrade must not leak the connection
        raise
    return conn


def _has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memories_fts'"
    ).fetchone()
    return row is not None


def _ensure_fts(conn: sqlite3.Connection) -> bool:
    """Create the FTS5 index and its sync triggers. Returns False if FTS5 is unavailable."""
    if _has_fts(conn):
        return True
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, category,
                content='memories', content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
    except sqlite3.OperationalError:
        return False
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, category)
            VALUES (new.id, new.content, new.category);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, category)
            VALUES ('delete', old.id, old.content, old.category);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content, category ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, category)
            VALUES ('delete', old.id, old.content, old.category);
            INSERT INTO memories_fts(rowid, content, category)
            VALUES (new.id, new.content, new.category);
        END;
    """)
    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
    return True


@contextmanager
def session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def rebuild_index(db_path: Path | None = None) -> bool:
    """Rebuild the FTS index from the memories table. False if FTS5 is unavailable."""
    with session(db_path) as conn:
        if not _has_fts(conn):
            return False
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
        return True