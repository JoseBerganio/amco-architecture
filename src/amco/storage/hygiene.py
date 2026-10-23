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

from pathlib import Path
from typing import Any

from .db import session
from .memories import list_memories
from .text import normalize_content, term_similarity

SIMILARITY_THRESHOLD = 0.6  # term overlap at which two memories count as "similar"


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