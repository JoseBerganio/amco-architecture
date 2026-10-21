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

# continue on the sprint 7

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import DEFAULT_DB, database_path  # noqa: F401  (re-exported, part of the public surface)
from .ranking import rank_memories

VALID_TYPES = ("persistent", "long_term")

from .ranking import rank_memories

VALID_TYPES = ("persistent", "long_term")
DEFAULT_CONFIDENCE = 1.0
MAX_QUERY_TERMS = 12
SIMILARITY_THRESHOLD = 0.6  # term overlap at which two memories count as "similar"

_FIELDS = (
    "id", "content", "category", "source", "memory_type",
    "confidence", "use_count", "created_at", "updated_at",
    "superseded_by", "superseded_at", "expires_at", "last_used_at",
)
_COLUMNS = ", ".join(_FIELDS)
_FTS_COLUMNS = ", ".join(f"m.{name}" for name in _FIELDS)

STOPWORDS = frozenset("""
a an the and or but if of to in on at by for with about as from into is are was were be been am
do does did it its this that these those i you he she we they me my your our their what which who
whom when where why how can could should would will shall may might must not no so than then there
here have has had any some please tell hi hello hey thanks thank ok okay
""".split())

_TOKEN_RE = re.compile(r"[^\W_]+")


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
    for name, ddl in (  # Sprint 5
        ("superseded_by", "INTEGER"),
        ("superseded_at", "TEXT"),
        ("expires_at", "TEXT"),
        ("last_used_at", "TEXT"),
    ):
        if name not in existing:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {ddl}")
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


def supersede_memory(old_id: int, new_id: int, db_path: Path | None = None) -> bool:
    """Mark `old_id` as replaced by `new_id`. Returns False if `old_id` does not exist."""
    if old_id == new_id:
        raise ValueError("A memory cannot supersede itself.")
    with session(db_path) as conn:
        new = conn.execute(
            "SELECT superseded_by FROM memories WHERE id = ?", (new_id,)
        ).fetchone()
        if new is None:
            raise ValueError(f"No memory found with ID #{new_id}.")
        if new["superseded_by"] is not None:
            raise ValueError(
                f"Memory #{new_id} is itself superseded; use its replacement instead."
            )
        old = conn.execute(
            "SELECT superseded_by FROM memories WHERE id = ?", (old_id,)
        ).fetchone()
        if old is None:
            return False
        if old["superseded_by"] is not None:
            raise ValueError(f"Memory #{old_id} is already superseded by #{old['superseded_by']}.")
        conn.execute(
            "UPDATE memories SET superseded_by = ?, superseded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_id, old_id),
        )
        return True


def restore_memory(memory_id: int, db_path: Path | None = None) -> bool:
    """Undo supersession. Returns False if the memory does not exist."""
    with session(db_path) as conn:
        cur = conn.execute(
            "UPDATE memories SET superseded_by = NULL, superseded_at = NULL WHERE id = ?",
            (memory_id,),
        )
        return cur.rowcount > 0


# --- Duplicates ------------------------------------------------------------


def normalize_content(text: str) -> str:
    """Case, whitespace and trailing punctuation do not make a memory different."""
    return " ".join(text.casefold().split()).rstrip(".!? ")


def term_similarity(a: str, b: str) -> float:
    """Jaccard overlap (0 to 1) of the meaningful terms of two texts."""
    terms_a, terms_b = set(extract_terms(a)), set(extract_terms(b))
    if not terms_a or not terms_b:
        return 0.0
    return len(terms_a & terms_b) / len(terms_a | terms_b)


def check_duplicates(
    content: str,
    db_path: Path | None = None,
    threshold: float = SIMILARITY_THRESHOLD,
    max_similar: int = 3,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return (exact duplicate or None, similar active memories, best first)."""
    key = normalize_content(content)
    if not key:
        return None, []
    exact: dict[str, Any] | None = None
    similar: list[dict[str, Any]] = []
    for memory in list_memories(db_path):
        if normalize_content(memory["content"]) == key:
            exact = exact or memory
            continue
        similarity = term_similarity(content, memory["content"])
        if similarity >= threshold:
            similar.append({**memory, "similarity": similarity})
    similar.sort(key=lambda m: m["similarity"], reverse=True)
    return exact, similar[:max_similar]


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
    """Retrieve unranked, active candidates, each with a positive `match_score`."""
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
                        WHERE memories_fts MATCH ? AND {_active_sql('m')}
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
    history: bool = False,
) -> list[dict[str, Any]]:
    """Full-text search over active memories, re-ranked by the Sprint 4 formula.

    `history=True` stops long-term memories being demoted (used for questions about the past).
    """
    limit = max(1, limit)
    candidates = search_candidates(query, pool=max(limit * 4, 20), db_path=db_path)
    return rank_memories(candidates, now=now, history=history)[:limit]


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


def rebuild_index(db_path: Path | None = None) -> bool:
    """Rebuild the FTS index from the memories table. False if FTS5 is unavailable."""
    with session(db_path) as conn:
        if not _has_fts(conn):
            return False
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
        return True