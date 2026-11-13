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

"""Score one observation against its query's labels. Pure: no database, no AME."""

from __future__ import annotations

from collections.abc import Sequence

from .fixture_types import FixtureQuery
from .metrics import (
    forbidden_hits,
    has_false_inclusion,
    is_hit,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from .results import Observation, QueryResult, ViewScores


def _view(expect: Sequence[str], ranked: Sequence[str], k: int) -> ViewScores:
    return ViewScores(
        recall=recall_at_k(expect, ranked, k),
        hit=is_hit(expect, ranked, k),
        reciprocal_rank=reciprocal_rank(expect, ranked, k),
        precision=precision_at_k(expect, ranked, k),
    )


def score_query(query: FixtureQuery, observation: Observation, k: int) -> QueryResult:
    """Candidates are judged in the top k. Selected memories are judged whole,
    because the model sees all of them."""
    selected = observation.selected
    selected_k = max(1, len(selected))
    return QueryResult(
        id=query.id,
        query=query.query,
        tags=query.tags,
        split=query.split,
        expect=query.expect,
        forbid=query.forbid,
        expect_kind=query.expect_kind,
        observation=observation,
        candidates=_view(query.expect, observation.candidates, k),
        selected=_view(query.expect, selected, selected_k),
        forbidden_selected=tuple(forbidden_hits(query.forbid, selected)),
        false_inclusion=None if query.expect else has_false_inclusion(selected),
        kind_ok=None if query.expect_kind is None else observation.kind == query.expect_kind,
        history_ok=observation.wants_history == query.history,
    )