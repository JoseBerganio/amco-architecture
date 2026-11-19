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
VALID_KINDS = ("fact", "summary", "record")
VALID_SOURCES = ("user", "chat", "summary")
DEFAULT_KIND = "fact"
DEFAULT_SOURCE = "user"
DEFAULT_CONFIDENCE = 1.0

# Kinds that belong in long-term memory unless the caller says otherwise (K8).
LONG_TERM_KINDS = frozenset({"summary", "record"})

_STAMP = "%Y-%m-%d %H:%M:%S"
_DAY = "%Y-%m-%d"

_FIELDS = (
    "id", "content", "category", "source", "memory_type",
    "confidence", "use_count", "created_at", "updated_at",
    "superseded_by", "superseded_at", "expires_at", "last_used_at",
    "kind", "source_session", "period_start", "period_end",
)
_COLUMNS = ", ".join(_FIELDS)


# --- Validation and status helpers -----------------------------------------


def _check_choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    value = value.strip().casefold()
    if value not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}.")
    return value


def _check_type(memory_type: str) -> str:
    return _check_choice(memory_type, VALID_TYPES, "Memory type")


def _check_kind(kind: str) -> str:
    return _check_choice(kind, VALID_KINDS, "Memory kind")


def _check_source(source: str) -> str:
    return _check_choice(source, VALID_SOURCES, "Memory source")


def _resolve_type(memory_type: str | None, kind: str) -> str:
    """An explicit type always wins; otherwise summaries and records are long-term."""
    if memory_type is None:
        return "long_term" if kind in LONG_TERM_KINDS else "persistent"
    return _check_type(memory_type)


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


def _period_bound(value: str, name: str, is_end: bool) -> tuple[str, datetime]:
    """Return (text to store, moment to compare). A date-only end runs to the end of that day."""
    text = value.strip()
    for fmt, has_time in ((_STAMP, True), (_DAY, False)):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        comparable = parsed
        if is_end and not has_time:
            comparable = parsed.replace(hour=23, minute=59, second=59)
        return parsed.strftime(fmt), comparable
    raise ValueError(f"{name} must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.")


def _check_period(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    """Validate an optional period. Blank counts as not given."""
    first = _period_bound(start, "Period start", False) if start and start.strip() else None
    last = _period_bound(end, "Period end", True) if end and end.strip() else None
    if first and last and first[1] > last[1]:
        raise ValueError("Period start cannot be after period end.")
    return (first[0] if first else None, last[0] if last else None)


def _clean_session(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


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
    memory_type: str | None = None,
    db_path: Path | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    expires_at: str | None = None,
    supersedes: int | None = None,
    kind: str = DEFAULT_KIND,
    source: str = DEFAULT_SOURCE,
    source_session: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> int:
    """Save a memory. If `supersedes` is given, the older memory is replaced atomically.

    `memory_type=None` picks the tier from the kind: summaries and records go to
    long-term memory, facts to persistent memory. An explicit type always wins.
    """
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    kind = _check_kind(kind)
    memory_type = _resolve_type(memory_type, kind)
    source = _check_source(source)
    confidence = _check_confidence(confidence)
    expires = _check_expiry(expires_at) if expires_at else None
    start, end = _check_period(period_start, period_end)
    session_id = _clean_session(source_session)
    with session(db_path) as conn:
        if supersedes is not None:
            _require_supersedable(conn, supersedes)
        cur = conn.execute(
            """INSERT INTO memories(content, category, source, memory_type, confidence,
                                    expires_at, updated_at, kind, source_session,
                                    period_start, period_end)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)""",
            (
                content, category.strip() or "general", source, memory_type, confidence,
                expires, kind, session_id, start, end,
            ),
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
    kind: str | None = None,
) -> bool:
    """Update the given fields. Returns False if the memory does not exist.

    For `expires_at`, pass a YYYY-MM-DD date to set it or "none" to clear it.
    Changing the kind never moves the memory between tiers; that is `memory_type`.
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
    if kind is not None:
        fields["kind"] = _check_kind(kind)
    if confidence is not None:
        fields["confidence"] = _check_confidence(confidence)
    if expires_at is not None:
        text = expires_at.strip()
        fields["expires_at"] = None if text.casefold() in {"", "none", "never"} else _check_expiry(text)
    if not fields:
        raise ValueError(
            "Nothing to update. Provide content, category, type, kind, confidence, or expiry."
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