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

from amco.evaluation import FixtureQuery, Observation, score_query


def _obs(**over) -> Observation:
    base = dict(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=(), selected=(), skipped=(), conflicts=(),
        memory_tokens=0, prompt_tokens=0, retrieval_ms=0.0, total_ms=0.0,
    )
    base.update(over)
    return Observation(**base)


def _q(**over) -> FixtureQuery:
    base = dict(id="q1", query="q?", tags=("exact",), split="train")
    base.update(over)
    return FixtureQuery(**base)


def test_hit_is_scored_in_both_views():
    r = score_query(_q(expect=("a",)), _obs(candidates=("a", "x"), selected=("a",)), k=5)
    assert r.candidates.hit is True
    assert r.candidates.recall == pytest.approx(1.0)
    assert r.candidates.reciprocal_rank == pytest.approx(1.0)
    assert r.candidates.precision == pytest.approx(0.5)
    assert r.selected.hit is True
    assert r.selected.precision == pytest.approx(1.0)


def test_candidates_are_cut_at_k_but_selected_is_judged_whole():
    obs = _obs(candidates=("x", "y", "a"), selected=("x", "y", "a"))
    r = score_query(_q(expect=("a",)), obs, k=2)
    assert r.candidates.hit is False and r.candidates.reciprocal_rank == 0.0
    assert r.selected.hit is True
    assert r.selected.reciprocal_rank == pytest.approx(1 / 3)


def test_negative_query_has_no_retrieval_metrics_but_has_false_inclusion():
    clean = score_query(_q(tags=("negative",)), _obs(), k=5)
    assert clean.candidates.recall is None and clean.selected.hit is None
    assert clean.false_inclusion is False
    noisy = score_query(_q(tags=("negative",)), _obs(selected=("z",)), k=5)
    assert noisy.false_inclusion is True


def test_expected_but_nothing_selected_is_a_miss_with_undefined_precision():
    r = score_query(_q(expect=("a",)), _obs(candidates=("x",)), k=5)
    assert r.selected.recall == 0.0 and r.selected.hit is False
    assert r.selected.precision is None
    assert r.false_inclusion is None  # only defined when nothing was expected


def test_forbid_is_checked_on_selected_only():
    q = _q(expect=("a",), forbid=("o",))
    in_candidates_only = score_query(q, _obs(candidates=("o", "a"), selected=("a",)), k=5)
    assert in_candidates_only.forbidden_selected == ()
    reached_prompt = score_query(q, _obs(candidates=("a", "o"), selected=("a", "o")), k=5)
    assert reached_prompt.forbidden_selected == ("o",)


def test_classifier_and_history_checks():
    assert score_query(_q(expect=("a",)), _obs(), k=5).kind_ok is None
    q = _q(expect=("a",), expect_kind="followup", history=True)
    r = score_query(q, _obs(kind="question", wants_history=True), k=5)
    assert r.kind_ok is False and r.history_ok is True
    assert score_query(q, _obs(kind="followup", wants_history=False), k=5).history_ok is False


def test_query_labels_are_carried_into_the_result():
    q = _q(expect=("a",), forbid=("b",), tags=("exact", "stem"), split="dev")
    r = score_query(q, _obs(), k=5)
    assert (r.id, r.tags, r.split, r.expect, r.forbid) == ("q1", ("exact", "stem"), "dev", ("a",), ("b",))