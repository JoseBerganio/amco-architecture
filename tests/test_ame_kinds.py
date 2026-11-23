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
from datetime import datetime, timezone
from pathlib import Path

import pytest

import amco.ame as ame
from amco.config import context_settings
from amco.evaluation import fts5_available
from amco.ranking import RankingWeights, rank_memories
from amco.storage import add_memory, search_candidates
from amco.summaries import summary_limit
from amco.working import WorkingMemory

PERIOD = {"period_start": "2026-11-19 09:00:00", "period_end": "2026-11-19 10:00:00"}
HISTORY_QUESTION = "What did we decide last time about storage?"


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _use_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    return db


# --- format_memory ----------------------------------------------------------------


def test_a_fact_line_is_exactly_what_it_always_was():
    memory = {"id": 3, "category": "tech", "content": "Uses SQLite"}
    assert ame.format_memory(memory) == "- [Memory 3 | tech] Uses SQLite"
    assert ame.format_memory({**memory, "kind": "fact", "period_start": "2026-11-19"}) == (
        "- [Memory 3 | tech] Uses SQLite"
    )
    assert ame.format_memory({**memory, "kind": None}) == "- [Memory 3 | tech] Uses SQLite"


def test_a_summary_line_shows_its_kind_and_day():
    memory = {"id": 7, "category": "session", "content": "We chose SQLite", "kind": "summary", **PERIOD}
    assert ame.format_memory(memory) == "- [Memory 7 | summary 2026-11-19 | session] We chose SQLite"


def test_a_record_without_a_period_shows_only_its_kind():
    memory = {"id": 9, "category": "ops", "content": "Migration done", "kind": "record"}
    assert ame.format_memory(memory) == "- [Memory 9 | record | ops] Migration done"


def test_a_multi_day_summary_shows_both_days():
    memory = {
        "id": 4, "category": "session", "content": "Week recap", "kind": "summary",
        "period_start": "2026-11-16", "period_end": "2026-11-20",
    }
    assert ame.format_memory(memory) == "- [Memory 4 | summary 2026-11-16..2026-11-20 | session] Week recap"