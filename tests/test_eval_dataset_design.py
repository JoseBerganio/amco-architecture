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

import pytest

from amco.evaluation import fts5_available, load_fixtures, run_suite

needs_fts5 = pytest.mark.skipif(not fts5_available(), reason="SQLite build has no FTS5")


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


@needs_fts5
def test_no_paraphrase_query_reaches_its_target_by_words():
    """The dataset promise: paraphrases miss under FTS5, so hybrid retrieval has something to win.

    Checked against the whole candidate pool, not only the top k, so a target retrieved at
    rank 7 (still a lexical path) is caught too. If this fails, the query is not a real
    paraphrase: fix its wording (a label fix, recorded in the change log), do not delete the test.
    """
    suite = run_suite(load_fixtures(), tags=["paraphrase"])
    assert len(suite.results) >= 8
    for r in suite.results:
        reached = set(r.expect) & set(r.observation.candidates)
        assert not reached, f"{r.id} retrieves {sorted(reached)} by words: {r.observation.search_text!r}"