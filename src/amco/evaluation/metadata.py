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


"""Describe the conditions of a run so a saved result can be reproduced and compared fairly.

Every setting is read through amco.config, the only module allowed to read the environment.
"""

from __future__ import annotations

import platform
import sqlite3
from collections.abc import Collection
from datetime import datetime, timezone

from .. import __version__
from ..ame import DEEP_DEPTH, DEFAULT_DEPTH, EXTRA_CANDIDATES
from ..config import (
    context_settings,
    followup_settings,
    freshness_half_life_days,
    ranking_weight_settings,
    set_amco_variables,
)
from .run_record import RunMeta

_WEIGHT_NAMES = ("relevance", "confidence", "freshness", "usefulness")


def fts5_available() -> bool:
    """True if this SQLite build can create an FTS5 table."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def collect_meta(
    *,
    mode: str = "fts",
    tags: Collection[str] | str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> RunMeta:
    """Snapshot the current settings. A naive `now` is taken to be UTC."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if isinstance(tags, str):
        tag_filter: tuple[str, ...] = (tags,)
    else:
        tag_filter = tuple(sorted(tags or ()))
    limit, reserved, memory_cap = context_settings()
    min_terms, turns = followup_settings()
    return RunMeta(
        amco_version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
        sqlite_version=sqlite3.sqlite_version,
        fts5=fts5_available(),
        mode=mode,
        ranking_weights=dict(zip(_WEIGHT_NAMES, ranking_weight_settings())),
        half_life_days=freshness_half_life_days(),
        context={"limit": limit, "reserved_output": reserved, "memory_cap": memory_cap},
        followup={"min_terms": min_terms, "turns": turns},
        retrieval={
            "default_depth": DEFAULT_DEPTH,
            "deep_depth": DEEP_DEPTH,
            "extra_candidates": EXTRA_CANDIDATES,
        },
        tags=tag_filter,
        amco_variables=set_amco_variables(),
        created_at=moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        note=note,
    )