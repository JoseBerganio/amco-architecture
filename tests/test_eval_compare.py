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

import os
from dataclasses import replace

import pytest

from amco.evaluation import (
    FixtureQuery,
    Observation,
    RunError,
    SavedRun,
    build_suite_result,
    collect_meta,
    compare_runs,
    score_query,
)


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _result(id, expect=(), forbid=(), selected=(), tags=("exact",)):
    observation = Observation(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=tuple(selected), selected=tuple(selected), skipped=(), conflicts=(),
        memory_tokens=10, prompt_tokens=100, retrieval_ms=1.0, total_ms=2.0,
    )
    query = FixtureQuery(
        id=id, query=f"query {id}", expect=tuple(expect), forbid=tuple(forbid),
        tags=tuple(tags), split="train",
    )
    return score_query(query, observation, 5)


def _hit(id):
    return _result(id, expect=["a"], selected=["a"])


def _miss(id):
    return _result(id, expect=["a"], selected=["x"])


def _run(results, digest="f" * 64, meta=None, k=5):
    return SavedRun(meta or collect_meta(), build_suite_result("fx", digest, k, list(results)))


def test_identical_runs_have_no_flips_no_setting_differences_and_meet_the_rule():
    meta = collect_meta()
    results = [_hit("q1"), _hit("q2"), _result("n1", tags=("negative",))]
    c = compare_runs(_run(results, meta=meta), _run(results, meta=meta))
    assert c.flips == () and c.settings == () and c.queries_compared == 3
    assert c.same_fixtures and c.ship_rule_ok is True and c.net("selected") == 0
    assert {m.verdict for m in c.metrics} <= {"same", "n/a"}


def test_one_lost_query_is_flagged_in_both_views_but_the_rule_still_holds():
    meta = collect_meta()
    a = _run([_hit("q1"), _hit("q2")], meta=meta)
    b = _run([_miss("q1"), _hit("q2")], meta=meta)
    c = compare_runs(a, b, "before", "after")
    assert {(f.view, f.id) for f in c.flips} == {("candidates", "q1"), ("selected", "q1")}
    assert (c.net("candidates"), c.net("selected")) == (-1, -1)
    assert c.count("selected", gained=False) == 1 and c.count("selected", gained=True) == 0
    assert c.ship_rule_ok is True
    assert next(m for m in c.metrics if m.label == "Selected hits").verdict == "worse"
    assert (c.a_label, c.b_label) == ("before", "after")


def test_two_net_lost_queries_break_the_ship_rule():
    meta = collect_meta()
    a = _run([_hit("q1"), _hit("q2")], meta=meta)
    b = _run([_miss("q1"), _miss("q2")], meta=meta)
    assert compare_runs(a, b).ship_rule_ok is False


def test_a_gain_offsets_a_loss():
    meta = collect_meta()
    a = _run([_miss("q1"), _hit("q2"), _hit("q3")], meta=meta)
    b = _run([_hit("q1"), _miss("q2"), _miss("q3")], meta=meta)
    c = compare_runs(a, b)
    assert c.net("selected") == -1 and c.count("selected", gained=True) == 1
    assert c.ship_rule_ok is True


def test_forbid_and_noise_flips_are_reported_but_not_counted_in_the_rule():
    meta = collect_meta()
    a = _run([
        _result("f1", expect=["a"], forbid=["o"], selected=["a"]),
        _result("n1", tags=("negative",)),
    ], meta=meta)
    b = _run([
        _result("f1", expect=["a"], forbid=["o"], selected=["a", "o"]),
        _result("n1", tags=("negative",), selected=["z"]),
    ], meta=meta)
    c = compare_runs(a, b)
    assert {f.view for f in c.flips} == {"forbid", "noise"}
    assert c.ship_rule_ok is True
    verdicts = {m.label: m.verdict for m in c.metrics}
    assert verdicts["Forbidden memories selected"] == "worse"
    assert verdicts["False inclusion"] == "worse"


def test_different_fixtures_are_refused_unless_forced():
    a = _run([_hit("q1"), _hit("q2")], digest="a" * 64)
    b = _run([_hit("q1"), _hit("q3")], digest="b" * 64)
    with pytest.raises(RunError, match="different fixtures"):
        compare_runs(a, b)
    c = compare_runs(a, b, force=True)
    assert not c.same_fixtures and c.queries_compared == 1
    assert c.only_in_a == ("q2",) and c.only_in_b == ("q3",)
    assert c.ship_rule_ok is None


def test_setting_differences_are_listed_but_never_block():
    meta = collect_meta()
    other = replace(meta, mode="hybrid", ranking_weights={**meta.ranking_weights, "relevance": 0.5})
    results = [_hit("q1")]
    c = compare_runs(_run(results, meta=meta), _run(results, meta=other, k=3))
    assert {d.field for d in c.settings} == {"mode", "ranking_weights", "k"}
    assert next(d for d in c.settings if d.field == "k") .after == "3"


def test_ratio_metrics_keep_raw_counts_and_report_a_change():
    meta = collect_meta()
    a = _run([_hit("q1"), _hit("q2")], meta=meta)
    b = _run([_hit("q1"), _miss("q2")], meta=meta)
    hits = next(m for m in compare_runs(a, b).metrics if m.label == "Candidate hits")
    assert hits.before == "2/2 (100.0%)" and hits.after == "1/2 (50.0%)"
    assert hits.delta == pytest.approx(-0.5)