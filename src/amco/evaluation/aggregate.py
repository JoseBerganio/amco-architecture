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

"""Combine query results into summaries. Pure: no database, no AME."""

from __future__ import annotations

from collections.abc import Sequence

from .metrics import describe, mean_defined, ratio
from .results import QueryResult, SuiteResult, Summary, ViewScores, ViewSummary

UNSPLIT = "unsplit"


def _view_summary(views: list[ViewScores]) -> ViewSummary:
    return ViewSummary(
        hits=ratio(v.hit for v in views),
        recall=mean_defined(v.recall for v in views),
        mrr=mean_defined(v.reciprocal_rank for v in views),
        precision=mean_defined(v.precision for v in views),
    )


def summarize(results: Sequence[QueryResult]) -> Summary:
    """Summarize any group of results (all, one tag, one split)."""
    obs = [r.observation for r in results]
    return Summary(
        queries=len(results),
        candidates=_view_summary([r.candidates for r in results]),
        selected=_view_summary([r.selected for r in results]),
        forbid_violations=ratio(bool(r.forbidden_selected) if r.forbid else None for r in results),
        false_inclusion=ratio(r.false_inclusion for r in results),
        classifier=ratio(r.kind_ok for r in results),
        history_labels=ratio(r.history_ok for r in results),
        memory_tokens=describe([o.memory_tokens for o in obs]),
        prompt_tokens=describe([o.prompt_tokens for o in obs]),
        retrieval_ms=describe([o.retrieval_ms for o in obs]),
        total_ms=describe([o.total_ms for o in obs]),
    )


def _grouped(results: Sequence[QueryResult], names) -> dict[str, Summary]:
    groups: dict[str, list[QueryResult]] = {}
    for r in results:
        for name in names(r):
            groups.setdefault(name, []).append(r)
    return {name: summarize(items) for name, items in sorted(groups.items())}


def summarize_by_tag(results: Sequence[QueryResult]) -> dict[str, Summary]:
    """One summary per tag. A query with two tags counts in both."""
    return _grouped(results, lambda r: r.tags)


def summarize_by_split(results: Sequence[QueryResult]) -> dict[str, Summary]:
    """One summary per split ('train', 'dev'); queries without a split go under 'unsplit'."""
    return _grouped(results, lambda r: (r.split or UNSPLIT,))


def build_suite_result(
    fixture_name: str, fixture_digest: str, k: int, results: Sequence[QueryResult]
) -> SuiteResult:
    return SuiteResult(
        fixture_name=fixture_name,
        fixture_hash=fixture_digest,
        k=k,
        results=tuple(results),
        overall=summarize(results),
        by_tag=summarize_by_tag(results),
        by_split=summarize_by_split(results),
    )