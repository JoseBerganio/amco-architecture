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

"""Run fixture queries through the real AME pipeline and score them.

The model is never called and ame.finish() is never called, so use_count stays
untouched and runs are repeatable.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Collection, Sequence
from datetime import datetime
from pathlib import Path

from .. import ame
from ..working import WorkingMemory
from .aggregate import build_suite_result
from .build import build_database
from .fixture_types import KNOWN_TAGS, FixtureQuery, FixtureSet
from .fixtures import fixture_hash
from .results import Observation, QueryResult, SuiteResult
from .scoring import score_query

DEFAULT_K = 5  # matches ame.DEFAULT_DEPTH (a test enforces it)

_ID_RE = re.compile(r"#(\d+)")


def _check_k(k: int) -> int:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a whole number of at least 1.")
    return k


def select_queries(
    fixtures: FixtureSet, tags: Collection[str] | str | None = None
) -> tuple[FixtureQuery, ...]:
    """Queries carrying at least one of `tags` (all queries when no tags are given)."""
    if not tags:
        return fixtures.queries
    wanted = {tags} if isinstance(tags, str) else set(tags)
    unknown = sorted(wanted - KNOWN_TAGS)
    if unknown:
        raise ValueError(f"Unknown tag(s): {', '.join(unknown)}.")
    chosen = tuple(q for q in fixtures.queries if wanted & set(q.tags))
    if not chosen:
        raise ValueError(f"No queries carry the tag(s): {', '.join(sorted(wanted))}.")
    return chosen


def _observe(report, key_by_id: dict[int, str]) -> Observation:
    """Translate an AME ContextReport into plain facts keyed by fixture key."""

    def keys(ids) -> tuple[str, ...]:
        return tuple(key_by_id[i] for i in ids)

    def name_ids(text: str) -> str:  # "duplicate of #3" -> "duplicate of logs-a"
        return _ID_RE.sub(lambda m: key_by_id.get(int(m.group(1)), m.group(0)), text)

    a = report.analysis
    return Observation(
        kind=a.kind,
        wants_history=a.wants_history,
        borrowed=a.borrowed_context,
        depth=a.limit,
        search_text=a.retrieval_query,
        candidates=keys(i for i, _ in report.candidates),
        selected=keys(report.selected),
        skipped=tuple((key_by_id[s["id"]], name_ids(s["reason"])) for s in report.skipped),
        conflicts=tuple((key_by_id[w], key_by_id[loser]) for w, loser in report.conflicts),
        memory_tokens=report.memory_tokens,
        prompt_tokens=report.prompt_tokens,
        retrieval_ms=report.retrieval_ms,
        total_ms=report.total_ms,
    )


def run_query(
    query: FixtureQuery, db_path: Path, key_by_id: dict[int, str], k: int
) -> QueryResult:
    """One query with a fresh Working Memory seeded from the fixture."""
    working = WorkingMemory()
    for turn in query.turns:
        working.add(turn.role, turn.content)
    working.set_task(query.task)
    prepared = ame.prepare(query.query, working, db_path=db_path)
    return score_query(query, _observe(prepared.report, key_by_id), k)


def _run_at(
    fixtures: FixtureSet,
    queries: Sequence[FixtureQuery],
    path: Path,
    k: int,
    now: datetime | None,
) -> SuiteResult:
    key_to_id = build_database(fixtures, path, now) # always ALL memories, even with a tag filter
    key_by_id = {memory_id: key for key, memory_id in key_to_id.items()}
    results = [run_query(q, path, key_by_id, k) for q in queries]
    return build_suite_result(fixtures.name, fixture_hash(fixtures), k, results)


def run_suite(
    fixtures: FixtureSet,
    k: int = DEFAULT_K,
    db_path: Path | str | None = None,
    tags: Collection[str] | str | None = None,
    now: datetime | None = None,
) -> SuiteResult:
    """Build a database from the fixtures, run the queries, score and summarize.

    db_path=None uses a temporary database that is deleted afterwards. With a path,
    the database is built there (it must be absent or empty) and kept for inspection.
    `tags` filters queries only; every memory is always built.
    """
    _check_k(k)
    queries = select_queries(fixtures, tags)
    if db_path is not None:
        return _run_at(fixtures, queries, Path(db_path), k, now)
    with tempfile.TemporaryDirectory(prefix="amco-eval-", ignore_cleanup_errors=True) as folder:
        return _run_at(fixtures, queries, Path(folder) / "eval.sqlite3", k, now)