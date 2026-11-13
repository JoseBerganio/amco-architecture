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

"""AMCO evaluation harness: fixtures, metrics, database builder, runner, scoring.

Store, compare and report arrive in Step 4. Everything public is re-exported here.
"""

from __future__ import annotations

from .aggregate import (
    build_suite_result,
    summarize,
    summarize_by_split,
    summarize_by_tag,
)
from .build import build_database
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
from .results import (
    Observation,
    QueryResult,
    SuiteResult,
    Summary,
    ViewScores,
    ViewSummary,
)
from .runner import DEFAULT_K, run_query, run_suite, select_queries
from .scoring import score_query

__all__ = [
    "DEFAULT_K",
    "KNOWN_TAGS",
    "Distribution",
    "FixtureError",
    "FixtureMemory",
    "FixtureQuery",
    "FixtureSet",
    "FixtureTurn",
    "Observation",
    "QueryResult",
    "Ratio",
    "SuiteResult",
    "Summary",
    "ViewScores",
    "ViewSummary",
    "build_database",
    "build_suite_result",
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
    "run_query",
    "run_suite",
    "score_query",
    "select_queries",
    "summarize",
    "summarize_by_split",
    "summarize_by_tag",
]