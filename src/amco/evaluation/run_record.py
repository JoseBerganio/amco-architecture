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

"""Types for a saved evaluation run. Data only."""

from __future__ import annotations

from dataclasses import dataclass

from .results import SuiteResult


class RunError(ValueError):
    """A saved run cannot be named, written, read or compared."""
        
    
@dataclass(frozen=True)
class RunMeta:
    """The conditions of a run. Without these a saved result cannot be reproduced."""

    amco_version: str
    python: str
    platform: str
    sqlite_version: str
    fts5: bool                          # False means the keyword fallback produced the numbers
    mode: str                           # "fts" now; Sprint 12 adds "hybrid"
    ranking_weights: dict[str, float]   # relevance, confidence, freshness, usefulness
    half_life_days: float
    context: dict[str, int]             # limit, reserved_output, memory_cap
    followup: dict[str, int]            # min_terms, turns
    retrieval: dict[str, int]           # default_depth, deep_depth, extra_candidates
    tags: tuple[str, ...]               # tag filter used (empty = every query)
    amco_variables: tuple[str, ...]     # names of AMCO_* settings that were set
    created_at: str                     # UTC, e.g. 2026-11-13T01:30:00Z
    note: str | None = None             # free text, for example a git commit or a purpose


@dataclass(frozen=True)
class SavedRun:
    """A run as stored: its conditions plus the scored suite.

    The run's name is the file name, so it is not stored inside the file.
    """

    meta: RunMeta
    suite: SuiteResult