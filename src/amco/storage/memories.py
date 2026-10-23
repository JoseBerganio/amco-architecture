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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .db import session

VALID_TYPES = ("persistent", "long_term")
DEFAULT_CONFIDENCE = 1.0

_FIELDS = (
    "id", "content", "category", "source", "memory_type",
    "confidence", "use_count", "created_at", "updated_at",
    "superseded_by", "superseded_at", "expires_at", "last_used_at",
)
_COLUMNS = ", ".join(_FIELDS)


# --- Validation and status helpers -----------------------------------------


def _check_type(memory_type: str) -> str:
    memory_type = memory_type.strip().casefold()
    if memory_type not in VALID_TYPES:
        raise ValueError(f"Memory type must be one of: {', '.join(VALID_TYPES)}.")
    return memory_type


def _check_confidence(value: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("Confidence must be a number between 0 and 1.") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError("Confidence must be a number between 0 and 1.")
    return value


def _check_expiry(value: str) -> str:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("Expiry must be a date in YYYY-MM-DD format.") from None


def _active_sql(alias: str = "") -> str:
    """SQL condition for memories that may be retrieved (not superseded, not expired)."""
    p = f"{alias}." if alias else ""
    return (
        f"{p}superseded_by IS NULL "
        f"AND ({p}expires_at IS NULL OR {p}expires_at >= date('now'))"
    )


def memory_status(memory: dict[str, Any], today: str | None = None) -> str:
    """Return 'superseded', 'expired' or 'active'."""
    if memory.get("superseded_by") is not None:
        return "superseded"
    expires = memory.get("expires_at")
    if expires and expires < (today or datetime.now(timezone.utc).date().isoformat()):
        return "expired"
    return "active"


def _require_supersedable(conn: sqlite3.Connection, old_id: int) -> None:
    row = conn.execute(
        "SELECT superseded_by FROM memories WHERE id = ?", (old_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No memory found with ID #{old_id}.")
    if row["superseded_by"] is not None:
        raise ValueError(f"Memory #{old_id} is already superseded by #{row['superseded_by']}.")


# --- CRUD ------------------------------------------------------------------


def add_memory(
    content: str,
    category: str = "general",
    memory_type: str = "persistent",
    db_path: Path | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    expires_at: str | None = None,
    supersedes: int | None = None,
) -> int:
    """Save a memory. If `supersedes` is given, the older memory is replaced atomically."""
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    memory_type = _check_type(memory_type)
    confidence = _check_confidence(confidence)
    expires = _check_expiry(expires_at) if expires_at else None
    with session(db_path) as conn:
        if supersedes is not None:
            _require_supersedable(conn, supersedes)
        cur = conn.execute(
            """INSERT INTO memories(content, category, source, memory_type, confidence,
                                    expires_at, updated_at)
               VALUES (?, ?, 'user', ?, ?, ?, CURRENT_TIMESTAMP)""",
            (content, category.strip() or "general", memory_type, confidence, expires),
        )
        new_id = int(cur.lastrowid)
        if supersedes is not None:
            conn.execute(
                "UPDATE memories SET superseded_by = ?, superseded_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (new_id, supersedes),
            )
        return new_id


def list_memories(
    db_path: Path | None = None,
    memory_type: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """List memories, newest first. Superseded and expired ones are hidden unless asked for."""
    query = f"SELECT {_COLUMNS} FROM memories"
    clauses: list[str] = []
    params: list[Any] = []
    if memory_type is not None:
        clauses.append("memory_type = ?")
        params.append(_check_type(memory_type))
    if not include_inactive:
        clauses.append(_active_sql())
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC"
    with session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_memory(memory_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    with session(db_path) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
    return dict(row) if row else None


def update_memory(
    memory_id: int,
    content: str | None = None,
    category: str | None = None,
    memory_type: str | None = None,
    db_path: Path | None = None,
    confidence: float | None = None,
    expires_at: str | None = None,
) -> bool:
    """Update the given fields. Returns False if the memory does not exist.

    For `expires_at`, pass a YYYY-MM-DD date to set it or "none" to clear it.
    """
    fields: dict[str, Any] = {}
    if content is not None:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty.")
        fields["content"] = content
    if category is not None:
        fields["category"] = category.strip() or "general"
    if memory_type is not None:
        fields["memory_type"] = _check_type(memory_type)
    if confidence is not None:
        fields["confidence"] = _check_confidence(confidence)
    if expires_at is not None:
        text = expires_at.strip()
        fields["expires_at"] = None if text.casefold() in {"", "none", "never"} else _check_expiry(text)
    if not fields:
        raise ValueError(
            "Nothing to update. Provide content, category, type, confidence, or expiry."
        )

    assignments = ", ".join(f"{name} = ?" for name in fields)
    with session(db_path) as conn:
        cur = conn.execute(
            f"UPDATE memories SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), memory_id),
        )
        return cur.rowcount > 0


def delete_memory(memory_id: int, db_path: Path | None = None) -> bool:
    """Delete a memory. Memories it had replaced are re-pointed to its own replacement,
    or revived if it had none, so a dangling link can never hide a memory forever."""
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT superseded_by FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False
        successor = row["superseded_by"]
        conn.execute(
            """UPDATE memories
               SET superseded_by = ?,
                   superseded_at = CASE WHEN ? IS NULL THEN NULL ELSE superseded_at END
               WHERE superseded_by = ?""",
            (successor, successor, memory_id),
        )
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return True


def record_usage(memory_ids: Iterable[int], db_path: Path | None = None) -> None:
    """Count one use (and stamp the time) for each memory that was sent to the model."""
    ids = sorted({int(i) for i in memory_ids})
    if not ids:
        return
    with session(db_path) as conn:
        conn.executemany(
            "UPDATE memories SET use_count = use_count + 1, last_used_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            [(i,) for i in ids],
        )