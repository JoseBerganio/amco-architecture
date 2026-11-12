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

from pathlib import Path

import amco.ame as ame
from amco.storage import add_memory, get_memory
from amco.working import WorkingMemory

QUESTION = "What is the project codename?"


def _eval_db(tmp_path: Path) -> tuple[Path, int]:
    db = tmp_path / "eval.sqlite3"
    memory_id = add_memory("The project codename is AMCO", db_path=db)
    return db, memory_id


def test_prepare_reads_the_given_database_and_never_opens_the_configured_one(
    tmp_path: Path, monkeypatch
):
    db, _ = _eval_db(tmp_path)
    configured = tmp_path / "configured.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(configured))

    prepared = ame.prepare(QUESTION, WorkingMemory(), db_path=db)

    assert [m["content"] for m in prepared.memories] == ["The project codename is AMCO"]
    assert not configured.exists()


def test_retrieve_accepts_db_path(tmp_path: Path, monkeypatch):
    db, _ = _eval_db(tmp_path)
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "configured.sqlite3"))
    analysis = ame.analyze_task(QUESTION, WorkingMemory())
    assert len(ame.retrieve(analysis, db_path=db)) == 1


def test_chitchat_skips_retrieval_even_with_a_db_path(tmp_path: Path):
    db, _ = _eval_db(tmp_path)
    analysis = ame.analyze_task("thanks!", WorkingMemory())
    assert ame.retrieve(analysis, db_path=db) == []


def test_prepare_alone_never_counts_usage(tmp_path: Path):
    db, memory_id = _eval_db(tmp_path)
    ame.prepare(QUESTION, WorkingMemory(), db_path=db)
    assert get_memory(memory_id, db_path=db)["use_count"] == 0


def test_default_behavior_is_unchanged(tmp_path: Path, monkeypatch):
    db, _ = _eval_db(tmp_path)
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    prepared = ame.prepare(QUESTION, WorkingMemory())
    assert len(prepared.memories) == 1