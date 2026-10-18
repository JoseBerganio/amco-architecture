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

from datetime import datetime, timedelta, timezone

import pytest

from amco.ranking import RankingWeights, freshness, rank_memories, usefulness, weights_from_env

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
FMT = "%Y-%m-%d %H:%M:%S"


def _mem(id, match=1.0, confidence=1.0, updated=None, memory_type="persistent", use_count=0):
    return {
        "id": id,
        "match_score": match,
        "confidence": confidence,
        "updated_at": updated or NOW.strftime(FMT),
        "memory_type": memory_type,
        "use_count": use_count,
    }


def test_freshness_halves_after_one_half_life():
    stamp = (NOW - timedelta(days=180)).strftime(FMT)
    assert freshness(stamp, NOW, 180.0) == pytest.approx(0.5)


def test_freshness_handles_future_and_unparseable_dates():
    assert freshness("2027-01-01 00:00:00", NOW, 180.0) == 1.0
    assert freshness("garbage", NOW, 180.0) == 0.5
    assert freshness(None, NOW, 180.0) == 0.5


def test_usefulness_combines_type_prior_and_usage():
    assert usefulness("persistent", 0) == pytest.approx(0.5)
    assert usefulness("long_term", 0) == pytest.approx(0.3)
    assert usefulness("persistent", 10) == pytest.approx(1.0)
    assert usefulness("persistent", 500) == pytest.approx(1.0)


def test_empty_candidates_return_empty_list():
    assert rank_memories([]) == []


def test_better_match_ranks_first_when_all_else_is_equal():
    ranked = rank_memories([_mem(1, match=1.0), _mem(2, match=2.0)], now=NOW)
    assert [m["id"] for m in ranked] == [2, 1]


def test_higher_confidence_ranks_first_when_relevance_is_equal():
    ranked = rank_memories([_mem(1, confidence=0.2), _mem(2, confidence=1.0)], now=NOW)
    assert [m["id"] for m in ranked] == [2, 1]


def test_old_relevant_memory_beats_recent_unrelated_one():
    old = _mem(1, match=1.0, updated=(NOW - timedelta(days=365)).strftime(FMT))
    recent = _mem(2, match=0.2)
    ranked = rank_memories([recent, old], now=NOW)
    assert ranked[0]["id"] == 1


def test_score_parts_are_exposed_for_diagnostics():
    ranked = rank_memories([_mem(1)], now=NOW)
    assert set(ranked[0]["score_parts"]) == {"relevance", "confidence", "freshness", "usefulness"}
    assert ranked[0]["score"] > 0


def test_custom_weights_change_the_order():
    only_confidence = RankingWeights(relevance=0, confidence=1, freshness=0, usefulness=0)
    ranked = rank_memories(
        [_mem(1, match=5.0, confidence=0.1), _mem(2, match=1.0, confidence=0.9)],
        weights=only_confidence,
        now=NOW,
    )
    assert [m["id"] for m in ranked] == [2, 1]


def test_weights_from_env(monkeypatch):
    monkeypatch.setenv("AMCO_WEIGHT_RELEVANCE", "0.9")
    monkeypatch.setenv("AMCO_WEIGHT_CONFIDENCE", "abc")
    monkeypatch.setenv("AMCO_WEIGHT_FRESHNESS", "-1")
    weights = weights_from_env()
    assert weights.relevance == 0.9
    assert weights.confidence == RankingWeights().confidence
    assert weights.freshness == RankingWeights().freshness
    
    
def test_history_flag_removes_the_long_term_demotion():
    assert usefulness("long_term", 0) == pytest.approx(0.3)
    assert usefulness("long_term", 0, history=True) == pytest.approx(0.5)


def test_rank_memories_with_history_favours_long_term_equally():
    persistent = _mem(1, memory_type="persistent")
    long_term = _mem(2, memory_type="long_term")
    normal = rank_memories([long_term, persistent], now=NOW)
    assert [m["id"] for m in normal] == [1, 2]
    history = rank_memories([long_term, persistent], now=NOW, history=True)
    assert history[0]["score"] == pytest.approx(history[1]["score"])