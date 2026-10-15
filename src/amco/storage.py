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
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from .ranking import rank_memories

DEFAULT_DB = Path.home() / ".amco" / "amco.sqlite3"
VALID_TYPES = ("persistent", "long_term")
DEFAULT_CONFIDENCE = 1.0
MAX_QUERY_TERMS = 12

_FIELDS = (
    "id", "content", "category", "source", "memory_type",
    "confidence", "use_count", "created_at", "updated_at",
)
_COLUMNS = ", ".join(_FIELDS)
_FTS_COLUMNS = ", ".join(f"m.{name}" for name in _FIELDS)

STOPWORDS = frozenset("""
a an the and or but if of to in on at by for with about as from into is are was were be been am
do does did it its this that these those i you he she we they me my your our their what which who
whom when where why how can could should would will shall may might must not no so than then there
here have has had any some please tell
""".split())

_TOKEN_RE = re.compile(r"[^\W_]+")


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
    _ensure_fts(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Upgrade databases created by earlier sprints in place."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
    if "updated_at" not in existing:
        conn.execute("ALTER TABLE memories ADD COLUMN updated_at TEXT")
    if "memory_type" not in existing:
        conn.execute(
            "ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'persistent'"
        )
    if "confidence" not in existing:  # Sprint 4
        conn.execute("ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0")
    if "use_count" not in existing:  # Sprint 4
        conn.execute("ALTER TABLE memories ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0")
    conn.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")


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


def add_memory(
    content: str,
    category: str = "general",
    memory_type: str = "persistent",
    db_path: Path | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
) -> int:
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    memory_type = _check_type(memory_type)
    confidence = _check_confidence(confidence)
    with session(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO memories(content, category, source, memory_type, confidence, updated_at)
               VALUES (?, ?, 'user', ?, ?, CURRENT_TIMESTAMP)""",
            (content, category.strip() or "general", memory_type, confidence),
        )
        return int(cur.lastrowid)


def list_memories(
    db_path: Path | None = None, memory_type: str | None = None
) -> list[dict[str, Any]]:
    query = f"SELECT {_COLUMNS} FROM memories"
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
) -> bool:
    """Update the given fields. Returns False if the memory does not exist."""
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
    if not fields:
        raise ValueError("Nothing to update. Provide content, category, type, or confidence.")

    assignments = ", ".join(f"{name} = ?" for name in fields)
    with session(db_path) as conn:
        cur = conn.execute(
            f"UPDATE memories SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), memory_id),
        )
        return cur.rowcount > 0


def delete_memory(memory_id: int, db_path: Path | None = None) -> bool:
    with session(db_path) as conn:
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0


# --- Retrieval -------------------------------------------------------------


def extract_terms(text: str, limit: int | None = None) -> list[str]:
    """Meaningful lowercase terms: no punctuation, stopwords, one-letter tokens or duplicates."""
    terms: list[str] = []
    for token in _TOKEN_RE.findall(text.casefold()):
        if len(token) < 2 or token in STOPWORDS or token in terms:
            continue
        terms.append(token)
    return terms if limit is None else terms[:limit]


def _fts_match(terms: list[str]) -> str:
    """Build a safe FTS5 query: every term quoted, joined with OR."""
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


def _keyword_candidates(terms: list[str], pool: int, db_path: Path | None) -> list[dict[str, Any]]:
    """Fallback used when the SQLite build has no FTS5."""
    found = []
    for memory in list_memories(db_path):
        content = memory["content"].casefold()
        score = sum(content.count(term) for term in terms)
        if score:
            found.append({**memory, "match_score": float(score)})
    found.sort(key=lambda m: (m["match_score"], m["id"]), reverse=True)
    return found[:pool]


def search_candidates(
    query: str, pool: int = 20, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Retrieve unranked candidates, each with a positive `match_score` (higher = better)."""
    terms = extract_terms(query, limit=MAX_QUERY_TERMS)
    if not terms:
        return []
    with session(db_path) as conn:
        if _has_fts(conn):
            try:
                rows = conn.execute(
                    f"""SELECT {_FTS_COLUMNS},
                               -bm25(memories_fts, 1.0, 0.5) AS match_score
                        FROM memories_fts
                        JOIN memories m ON m.id = memories_fts.rowid
                        WHERE memories_fts MATCH ?
                        ORDER BY match_score DESC
                        LIMIT ?""",
                    (_fts_match(terms), pool),
                ).fetchall()
                return [dict(row) for row in rows]
            except sqlite3.OperationalError:
                pass  # FTS5 module missing in this build: use the fallback below
    return _keyword_candidates(terms, pool, db_path)


def search_memories(
    query: str,
    limit: int = 5,
    db_path: Path | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Full-text search, re-ranked by relevance, confidence, freshness and usefulness."""
    limit = max(1, limit)
    candidates = search_candidates(query, pool=max(limit * 4, 20), db_path=db_path)
    return rank_memories(candidates, now=now)[:limit]


def record_usage(memory_ids: Iterable[int], db_path: Path | None = None) -> None:
    """Count one use for each memory that was sent to the model."""
    ids = sorted({int(i) for i in memory_ids})
    if not ids:
        return
    with session(db_path) as conn:
        conn.executemany(
            "UPDATE memories SET use_count = use_count + 1 WHERE id = ?",
            [(i,) for i in ids],
        )


def rebuild_index(db_path: Path | None = None) -> bool:
    """Rebuild the FTS index from the memories table. False if FTS5 is unavailable."""
    with session(db_path) as conn:
        if not _has_fts(conn):
            return False
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
        return True