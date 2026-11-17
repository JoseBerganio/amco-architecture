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

import io
import os
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console

from amco.evaluation import (
    FixtureQuery,
    Observation,
    RunListing,
    SavedRun,
    build_suite_result,
    collect_meta,
    compare_runs,
    render_comparison,
    render_run,
    render_run_list,
    score_query,
)


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _text(renderable) -> str:
    console = Console(file=io.StringIO(), width=200, force_terminal=False, color_system=None)
    console.print(renderable)
    return console.file.getvalue()


def _result(id, expect=(), selected=(), candidates=None, query=None, tags=("exact",)):
    observation = Observation(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=tuple(selected if candidates is None else candidates), selected=tuple(selected),
        skipped=(), conflicts=(), memory_tokens=10, prompt_tokens=100, retrieval_ms=1.0, total_ms=2.0,
    )
    q = FixtureQuery(id=id, query=query or f"query {id}", expect=tuple(expect), tags=tuple(tags), split="train")
    return score_query(q, observation, 5)


def _hit(id):
    return _result(id, expect=["a"], selected=["a"])


def _miss(id, query=None):
    return _result(id, expect=["a"], selected=["x"], query=query)


def _run(results, meta=None):
    return SavedRun(meta or collect_meta(), build_suite_result("fx", "f" * 64, 5, list(results)))


def test_a_run_shows_raw_counts_tags_and_splits():
    out = _text(render_run(_run([_hit("q1"), _miss("q2"), _result("n1", tags=("negative",))]), name="demo"))
    assert "Run: demo" in out and "Retrieval (k=5)" in out
    assert "1/2 (50.0%)" in out
    assert "By tag" in out and "negative" in out and "By split" in out and "train" in out
    assert "Queries needing attention" not in out


def test_verbose_lists_problems_with_found_counts():
    run = _run([_result("c1", expect=["a", "b"], selected=["a", "x"]), _hit("ok")])
    out = _text(render_run(run, verbose=True))
    assert "Queries needing attention: 1 of 2" in out
    assert "candidates: found 1 of 2 expected in the top 5" in out
    assert "expected:   a, b" in out and "1. a, 2. x" in out


def test_query_text_is_never_read_as_markup():
    out = _text(render_run(_run([_miss("q1", query="What is [bold]x[/bold]?")]), verbose=True))
    assert "[bold]x[/bold]" in out


def test_environment_and_fallback_warnings_are_visible():
    meta = replace(collect_meta(), amco_variables=("AMCO_MODEL",), fts5=False, note="trial")
    out = _text(render_run(_run([_hit("q1")], meta=meta)))
    assert "AMCO_MODEL" in out and "keyword fallback" in out and "Note: trial" in out


def test_comparison_shows_flips_changes_and_the_ship_rule():
    meta = collect_meta()
    a = _run([_hit("q1"), _hit("q2")], meta=meta)
    one_lost = compare_runs(a, _run([_miss("q1"), _hit("q2")], meta=meta), "base", "tuned")
    out = _text(render_comparison(one_lost))
    assert "Comparing base -> tuned" in out and "worse" in out and "q1" in out
    assert "met." in out and "NOT met" not in out

    two_lost = compare_runs(a, _run([_miss("q1"), _miss("q2")], meta=meta))
    assert "NOT met" in _text(render_comparison(two_lost))


def test_comparison_of_identical_runs_says_nothing_changed():
    meta = collect_meta()
    run = _run([_hit("q1")], meta=meta)
    out = _text(render_comparison(compare_runs(run, run)))
    assert "No query changed status." in out


def test_run_list_shows_runs_errors_and_the_empty_case():
    ok = RunListing(
        name="base", path=Path("base.json"), created_at="2026-11-13T00:00:00Z",
        fixture_name="default", fixture_hash="a" * 64, k=5,
        candidate_hits="1/2 (50.0%)", selected_hits="1/2 (50.0%)",
    )
    bad = RunListing(name="bad", path=Path("bad.json"), error="not valid JSON")
    out = _text(render_run_list([ok, bad], "runs"))
    assert "base" in out and "1/2 (50.0%)" in out and "unreadable: not valid JSON" in out
    assert "No saved runs in runs." in _text(render_run_list([], "runs"))