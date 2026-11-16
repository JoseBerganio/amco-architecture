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

"""The committed baseline freezes the default dataset and guards retrieval.

Re-baselining is an explicit act: after a deliberate dataset or retrieval change,
save a NEW run into benchmarks/ (keep the old files as history) and record why.
The newest FTS baseline, by creation time, is the one that counts.
"""

import os
from pathlib import Path

import pytest

from amco.evaluation import (
    DEFAULT_K,
    SavedRun,
    collect_meta,
    compare_runs,
    fixture_hash,
    fts5_available,
    load_fixtures,
    load_run_file,
    run_suite,
)

BENCHMARKS = Path(__file__).parent.parent / "benchmarks"

needs_fts5 = pytest.mark.skipif(not fts5_available(), reason="SQLite build has no FTS5")


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _latest_fts_baseline() -> tuple[str, SavedRun]:
    found = []
    for path in sorted(BENCHMARKS.glob("*.json")):
        run = load_run_file(path)
        if run.meta.mode == "fts" and not run.meta.tags:
            found.append((run.meta.created_at, path.name, run))
    assert found, (
        "No FTS baseline in benchmarks/. Create one with: "
        "amco eval run --save fts-baseline --out benchmarks/fts-baseline-0.6.json"
    )
    _, name, run = max(found, key=lambda item: (item[0], item[1]))
    return name, run


def test_the_dataset_matches_the_latest_baseline():
    name, baseline = _latest_fts_baseline()
    current = fixture_hash(load_fixtures())
    assert baseline.suite.fixture_hash == current, (
        f"The default dataset changed since {name} "
        f"({baseline.suite.fixture_hash[:12]} -> {current[:12]}). Fixtures are frozen per "
        "version: record a re-baseline by saving a new run into benchmarks/."
    )


def test_the_baseline_was_made_under_plain_default_conditions():
    name, baseline = _latest_fts_baseline()
    meta = baseline.meta
    assert baseline.suite.fixture_name == "default", name
    assert baseline.suite.k == DEFAULT_K
    assert meta.fts5 is True, "A baseline must come from FTS5, not the keyword fallback."
    assert meta.amco_variables == (), f"{name} was made with AMCO_* settings: {meta.amco_variables}"


@needs_fts5
def test_current_retrieval_meets_the_ship_rule_against_the_baseline():
    name, baseline = _latest_fts_baseline()
    now = SavedRun(collect_meta(), run_suite(load_fixtures()))
    comparison = compare_runs(baseline, now, name, "now")
    lost = [(f.view, f.id) for f in comparison.flips if not f.after]
    assert comparison.ship_rule_ok is True, (
        f"Retrieval lost more than 1 net query against {name}: {lost}. "
        "Fix the regression, or re-baseline deliberately."
    )