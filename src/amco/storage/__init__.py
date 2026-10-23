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

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..config import DEFAULT_DB, database_path  # noqa: F401  (re-exported, part of the public surface)
from ..ranking import rank_memories

from .text import STOPWORDS, extract_terms, normalize_content, term_similarity
from .db import _has_fts, connect, rebuild_index, session

from .memories import (
    DEFAULT_CONFIDENCE,
    VALID_TYPES,
    _FIELDS,
    _active_sql,
    add_memory,
    delete_memory,
    get_memory,
    list_memories,
    memory_status,
    record_usage,
    update_memory,
)

MAX_QUERY_TERMS = 12
SIMILARITY_THRESHOLD = 0.6  # term overlap at which two memories count as "similar"

_FTS_COLUMNS = ", ".join(f"m.{name}" for name in _FIELDS)

# --- CRUD ------------------------------------------------------------------

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
