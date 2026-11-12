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

"""AMCO evaluation harness: fixtures and metrics now; runner, store and reports in later steps.

Everything public is re-exported here.
"""

from __future__ import annotations

from .fixture_parse import parse_fixtures
from .fixture_types import (
    KNOWN_TAGS,
    FixtureError,
    FixtureMemory,
    FixtureQuery,
    FixtureSet,
    FixtureTurn,
)
from .fixtures import canonical_json, fixture_hash, load_fixtures

from .metrics import (
    Distribution,
    Ratio,
    describe,
    forbidden_hits,
    has_false_inclusion,
    is_hit,
    mean_defined,
    percentile,
    precision_at_k,
    ratio,
    recall_at_k,
    reciprocal_rank,
)

__all__ = [
    "KNOWN_TAGS",
    "Distribution",
    "FixtureError",
    "FixtureMemory",
    "FixtureQuery",
    "FixtureSet",
    "FixtureTurn",
    "Ratio",
    "canonical_json",
    "describe",
    "fixture_hash",
    "forbidden_hits",
    "has_false_inclusion",
    "is_hit",
    "load_fixtures",
    "mean_defined",
    "parse_fixtures",
    "percentile",
    "precision_at_k",
    "ratio",
    "recall_at_k",
    "reciprocal_rank",
]