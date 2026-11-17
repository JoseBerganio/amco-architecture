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

"""Build a throwaway database from a FixtureSet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..storage import add_memory, session
from .fixture_types import FixtureSet

_STAMP = "%Y-%m-%d %H:%M:%S"  # the format ranking.parse_timestamp reads


def _as_utc(moment: datetime | None) -> datetime:
    """Default to now. A naive datetime is taken to be UTC."""
    if moment is None:
        return datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def build_database(
    fixtures: FixtureSet, path: Path | str, now: datetime | None = None
) -> dict[str, int]:
    """Create every fixture memory in a fresh database and return {key: id}.

    Memories go through the normal add_memory(), so validation, supersession and
    the full-text index behave exactly as in real use. Then ONE documented UPDATE
    backdates created_at and updated_at from age_days and sets use_count, which
    add_memory() has no argument for. superseded_at keeps the real clock: no
    retrieval path reads it.

    Expiry dates are computed in UTC because SQLite's date('now') is UTC.
    The target must be absent or empty; evaluation never mixes into real data.
    """
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        raise ValueError(f"{path} already contains data; evaluation needs a fresh database.")

    moment = _as_utc(now)
    today = moment.date()
    ids: dict[str, int] = {}
    for memory in fixtures.memories:  # definition order guarantees `supersedes` targets exist
        expires = None
        if memory.expires_in_days is not None:
            expires = (today + timedelta(days=memory.expires_in_days)).isoformat()
        ids[memory.key] = add_memory(
            memory.content,
            category=memory.category,
            memory_type=memory.memory_type,
            db_path=path,
            confidence=memory.confidence,
            expires_at=expires,
            supersedes=ids[memory.supersedes] if memory.supersedes else None,
        )

    rows = []
    for memory in fixtures.memories:
        stamp = (moment - timedelta(days=memory.age_days)).strftime(_STAMP)
        rows.append((stamp, stamp, memory.use_count, ids[memory.key]))
    with session(path) as conn:
        conn.executemany(
            "UPDATE memories SET created_at = ?, updated_at = ?, use_count = ? WHERE id = ?",
            rows,
        )
    return ids