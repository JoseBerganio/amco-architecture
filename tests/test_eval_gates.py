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

import pytest

from amco.evaluation import FixtureQuery, Observation, check_gates, score_query, summarize


def _result(id, expect=(), selected=(), tags=("exact",)):
    observation = Observation(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=tuple(selected), selected=tuple(selected), skipped=(), conflicts=(),
        memory_tokens=0, prompt_tokens=0, retrieval_ms=0.0, total_ms=0.0,
    )
    query = FixtureQuery(id=id, query=id, expect=tuple(expect), tags=tuple(tags), split="train")
    return score_query(query, observation, 5)


def _half_and_half():
    """One hit and one miss: recall 0.5 and MRR 0.5."""
    return summarize([_result("h", ["a"], ["a"]), _result("m", ["a"], ["x"])])


def test_no_thresholds_means_no_failures():
    assert check_gates(_half_and_half()) == []


def test_a_threshold_equal_to_the_value_passes():
    assert check_gates(_half_and_half(), min_recall=0.5, min_mrr=0.5) == []


def test_below_a_threshold_fails_with_both_numbers_in_the_message():
    failures = check_gates(_half_and_half(), min_recall=0.6)
    assert len(failures) == 1
    assert "candidate recall 0.500 is below the required 0.600" in failures[0]


def test_each_failing_threshold_is_reported():
    assert len(check_gates(_half_and_half(), min_recall=0.9, min_mrr=0.9)) == 2


def test_an_undefined_metric_cannot_meet_a_threshold():
    only_negatives = summarize([_result("n", tags=("negative",))])
    failures = check_gates(only_negatives, min_recall=0.1)
    assert len(failures) == 1 and "undefined" in failures[0]
    assert check_gates(only_negatives) == []  # but without a threshold it is fine


def test_a_perfect_run_passes_the_strictest_gate():
    perfect = summarize([_result("h", ["a"], ["a"])])
    assert check_gates(perfect, min_recall=1.0, min_mrr=1.0) == []