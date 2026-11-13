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

from amco.evaluation import (
    FixtureQuery,
    Observation,
    Ratio,
    score_query,
    summarize,
    summarize_by_split,
    summarize_by_tag,
)


def _run(id, expect=(), forbid=(), tags=("exact",), split="train", expect_kind=None, **over):
    base = dict(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=(), selected=(), skipped=(), conflicts=(),
        memory_tokens=0, prompt_tokens=0, retrieval_ms=0.0, total_ms=0.0,
    )
    base.update(over)
    query = FixtureQuery(
        id=id, query=id, expect=tuple(expect), forbid=tuple(forbid),
        tags=tuple(tags), split=split, expect_kind=expect_kind,
    )
    return score_query(query, Observation(**base), k=5)


def test_overall_counts_hits_and_skips_negatives():
    results = [
        _run("hit", expect=["a"], candidates=("a",), selected=("a",)),
        _run("miss", expect=["a"], candidates=("x",), selected=("x",)),
        _run("neg-clean", tags=("negative",)),
        _run("neg-noisy", tags=("negative",), selected=("z",)),
    ]
    s = summarize(results)
    assert s.queries == 4
    assert s.candidates.hits == Ratio(1, 2)
    assert s.candidates.recall == pytest.approx(0.5)
    assert s.candidates.mrr == pytest.approx(0.5)
    assert s.candidates.precision == pytest.approx(0.5)
    assert s.false_inclusion == Ratio(1, 2)


def test_forbid_violations_count_only_queries_that_set_forbid():
    results = [
        _run("bad", expect=["a"], forbid=["o"], candidates=("a", "o"), selected=("a", "o")),
        _run("good", expect=["a"], forbid=["o"], candidates=("a",), selected=("a",)),
        _run("no-forbid", expect=["a"], candidates=("a",), selected=("a",)),
    ]
    assert summarize(results).forbid_violations == Ratio(1, 2)


def test_classifier_and_history_ratios():
    results = [
        _run("k1", expect=["a"], expect_kind="question", kind="question"),
        _run("k2", expect=["a"], expect_kind="followup", kind="question"),
        _run("k3", expect=["a"]),
    ]
    s = summarize(results)
    assert s.classifier == Ratio(1, 2)
    assert s.history_labels == Ratio(3, 3)


def test_distributions_come_from_the_observations():
    results = [
        _run("a", expect=["a"], memory_tokens=10, total_ms=1.0),
        _run("b", expect=["a"], memory_tokens=30, total_ms=3.0),
    ]
    s = summarize(results)
    assert s.memory_tokens.mean == pytest.approx(20.0)
    assert s.memory_tokens.maximum == pytest.approx(30.0)
    assert s.total_ms.p50 == pytest.approx(2.0)


def test_a_query_with_two_tags_counts_in_both_groups():
    results = [
        _run("both", expect=["a"], tags=("exact", "stem"), candidates=("a",), selected=("a",)),
        _run("one", expect=["a"], tags=("stem",), candidates=("x",), selected=("x",)),
    ]
    by_tag = summarize_by_tag(results)
    assert list(by_tag) == ["exact", "stem"]
    assert by_tag["exact"].candidates.hits == Ratio(1, 1)
    assert by_tag["stem"].candidates.hits == Ratio(1, 2)


def test_split_groups_and_unsplit():
    results = [
        _run("t", expect=["a"], split="train"),
        _run("d", expect=["a"], split="dev"),
        _run("u", expect=["a"], split=None),
    ]
    assert list(summarize_by_split(results)) == ["dev", "train", "unsplit"]


def test_empty_results_summarize_cleanly():
    s = summarize([])
    assert s.queries == 0
    assert s.candidates.hits == Ratio(0, 0)
    assert s.candidates.recall is None and s.candidates.mrr is None
    assert s.memory_tokens.count == 0