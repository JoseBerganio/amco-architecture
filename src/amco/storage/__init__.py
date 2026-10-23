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
from .hygiene import SIMILARITY_THRESHOLD, check_duplicates, restore_memory, supersede_memory

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
_FTS_COLUMNS = ", ".join(f"m.{name}" for name in _FIELDS)


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
