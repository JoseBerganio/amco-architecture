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

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB = Path.home() / ".amco" / "amco.sqlite3"
VALID_TYPES = ("persistent", "long_term")


def database_path() -> Path:
    raw = os.getenv("AMCO_DB_PATH")
    return Path(raw).expanduser() if raw else DEFAULT_DB


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add Sprint 2 columns to databases created by Sprint 1."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
    if "updated_at" not in existing:
        conn.execute("ALTER TABLE memories ADD COLUMN updated_at TEXT")
    if "memory_type" not in existing:
        conn.execute(
            "ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'persistent'"
        )
    conn.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")


@contextmanager
def session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _check_type(memory_type: str) -> str:
    memory_type = memory_type.strip().casefold()
    if memory_type not in VALID_TYPES:
        raise ValueError(f"Memory type must be one of: {', '.join(VALID_TYPES)}.")
    return memory_type


def add_memory(
    content: str,
    category: str = "general",
    memory_type: str = "persistent",
    db_path: Path | None = None,
) -> int:
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    memory_type = _check_type(memory_type)
    with session(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO memories(content, category, source, memory_type, updated_at)
               VALUES (?, ?, 'user', ?, CURRENT_TIMESTAMP)""",
            (content, category.strip() or "general", memory_type),
        )
        return int(cur.lastrowid)


def list_memories(
    db_path: Path | None = None, memory_type: str | None = None
) -> list[dict[str, Any]]:
    query = (
        "SELECT id, content, category, source, memory_type, created_at, updated_at "
        "FROM memories"
    )
    params: tuple = ()
    if memory_type is not None:
        query += " WHERE memory_type = ?"
        params = (_check_type(memory_type),)
    query += " ORDER BY id DESC"
    with session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_memory(memory_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT id, content, category, source, memory_type, created_at, updated_at "
            "FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
    return dict(row) if row else None


def update_memory(
    memory_id: int,
    content: str | None = None,
    category: str | None = None,
    memory_type: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Update the given fields. Returns False if the memory does not exist."""
    fields: dict[str, str] = {}
    if content is not None:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty.")
        fields["content"] = content
    if category is not None:
        fields["category"] = category.strip() or "general"
    if memory_type is not None:
        fields["memory_type"] = _check_type(memory_type)
    if not fields:
        raise ValueError("Nothing to update. Provide content, category, or type.")

    assignments = ", ".join(f"{name} = ?" for name in fields)
    with session(db_path) as conn:
        cur = conn.execute(
            f"UPDATE memories SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), memory_id),
        )
        return cur.rowcount > 0


def search_memories(query: str, limit: int = 5, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Simple case-insensitive keyword retrieval baseline; semantic search comes later."""
    terms = [term.casefold() for term in query.split() if len(term) > 1]
    if not terms:
        return []
    ranked = []
    for memory in list_memories(db_path):
        content = memory["content"].casefold()
        score = sum(content.count(term) for term in terms)
        if score:
            ranked.append((score, memory))
    ranked.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
    return [memory for _, memory in ranked[:max(1, limit)]]


def delete_memory(memory_id: int, db_path: Path | None = None) -> bool:
    with session(db_path) as conn:
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0