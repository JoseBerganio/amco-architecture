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

"""Sprint 11a regression gate (K14).

The long-term-memory fixtures add memories to the same database the original
queries search. This test proves they did not change the status of a single
original query, judged against the committed 0.6 baseline.
"""

import os
from pathlib import Path

import pytest

from amco.evaluation import (
    SavedRun,
    collect_meta,
    compare_runs,
    fts5_available,
    load_fixtures,
    load_run_file,
    run_suite,
)

BASELINE = Path(__file__).parent.parent / "benchmarks" / "fts-baseline-0.6.json"

needs_fts5 = pytest.mark.skipif(not fts5_available(), reason="SQLite build has no FTS5")


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


@needs_fts5
def test_the_ltm_fixtures_do_not_change_any_original_query():
    baseline = load_run_file(BASELINE)
    fixtures = load_fixtures()
    now = SavedRun(collect_meta(), run_suite(fixtures))

    comparison = compare_runs(baseline, now, "baseline-0.6", "now", force=True)

    lost_or_gained = [(f.view, f.id, f.before, f.after) for f in comparison.flips]
    assert lost_or_gained == [], (
        "The LTM fixtures changed the status of an original query: "
        f"{lost_or_gained}. Review it before accepting (S11-20)."
    )
    assert comparison.only_in_a == ()
    assert set(comparison.only_in_b) == {q.id for q in fixtures.queries if "ltm" in q.tags}