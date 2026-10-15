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

import amco.engine as engine
from amco.storage import add_memory, get_memory
from amco.working import WorkingMemory


def _history() -> WorkingMemory:
    wm = WorkingMemory()
    wm.add("user", "What database does AMCO use?")
    wm.add("assistant", "SQLite.")
    return wm


def test_thin_followup_borrows_terms_from_recent_user_turns():
    rq = engine.retrieval_query("Is it fast?", _history())
    assert rq.startswith("Is it fast?")
    assert "database" in rq


def test_detailed_question_is_left_alone():
    q = "Please describe the context budget algorithm"
    assert engine.retrieval_query(q, _history()) == q


def test_followup_without_history_is_unchanged():
    assert engine.retrieval_query("Is it fast?", WorkingMemory()) == "Is it fast?"


def test_followup_retrieves_memory_from_previous_topic(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    add_memory("The database is SQLite", db_path=db)
    monkeypatch.setattr(engine, "ollama_chat", lambda messages: "ok")

    _, used = engine.answer("Is it fast?", _history())
    assert [m["content"] for m in used] == ["The database is SQLite"]


def test_selected_memories_are_counted_as_used(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    memory_id = add_memory("The project codename is AMCO", db_path=db)
    monkeypatch.setattr(engine, "ollama_chat", lambda messages: "ok")

    engine.answer("What is the project codename?")
    assert get_memory(memory_id, db_path=db)["use_count"] == 1


def test_failed_model_call_does_not_count_usage(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    memory_id = add_memory("The project codename is AMCO", db_path=db)

    def boom(messages):
        raise RuntimeError("Ollama is down")

    monkeypatch.setattr(engine, "ollama_chat", boom)
    try:
        engine.answer("What is the project codename?")
    except RuntimeError:
        pass
    assert get_memory(memory_id, db_path=db)["use_count"] == 0