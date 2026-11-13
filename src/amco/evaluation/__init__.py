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


"""AMCO evaluation harness: fixtures, metrics, runner, saved runs, comparison and reports.

The `amco eval` CLI arrives in Step 5. Everything public is re-exported here.
"""

from __future__ import annotations

from .aggregate import (
    build_suite_result,
    summarize,
    summarize_by_split,
    summarize_by_tag,
)
from .build import build_database
from .compare import Comparison, Flip, MetricDelta, SettingDiff, compare_runs
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
from .metadata import collect_meta, fts5_available
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
from .report import (
    query_problems,
    render_comparison,
    render_problems,
    render_run,
    render_run_list,
)
from .results import (
    Observation,
    QueryResult,
    SuiteResult,
    Summary,
    ViewScores,
    ViewSummary,
)
from .run_record import RunError, RunMeta, SavedRun
from .runner import DEFAULT_K, run_query, run_suite, select_queries
from .scoring import score_query
from .serialize import FORMAT_VERSION, dumps_run, loads_run
from .store import (
    RunListing,
    check_name,
    list_runs,
    load_run,
    load_run_file,
    resolve_run,
    run_path,
    save_run,
    saved_names,
    write_run_file,
)

__all__ = [
    "DEFAULT_K",
    "FORMAT_VERSION",
    "KNOWN_TAGS",
    "Comparison",
    "Distribution",
    "FixtureError",
    "FixtureMemory",
    "FixtureQuery",
    "FixtureSet",
    "FixtureTurn",
    "Flip",
    "MetricDelta",
    "Observation",
    "QueryResult",
    "Ratio",
    "RunError",
    "RunListing",
    "RunMeta",
    "SavedRun",
    "SettingDiff",
    "SuiteResult",
    "Summary",
    "ViewScores",
    "ViewSummary",
    "build_database",
    "build_suite_result",
    "canonical_json",
    "check_name",
    "collect_meta",
    "compare_runs",
    "describe",
    "dumps_run",
    "fixture_hash",
    "forbidden_hits",
    "fts5_available",
    "has_false_inclusion",
    "is_hit",
    "list_runs",
    "load_fixtures",
    "load_run",
    "load_run_file",
    "loads_run",
    "mean_defined",
    "parse_fixtures",
    "percentile",
    "precision_at_k",
    "query_problems",
    "ratio",
    "recall_at_k",
    "reciprocal_rank",
    "render_comparison",
    "render_problems",
    "render_run",
    "render_run_list",
    "resolve_run",
    "run_path",
    "run_query",
    "run_suite",
    "save_run",
    "saved_names",
    "score_query",
    "select_queries",
    "summarize",
    "summarize_by_split",
    "summarize_by_tag",
    "write_run_file",
]