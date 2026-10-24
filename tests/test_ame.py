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
import amco.engine as engine
from amco.storage import add_memory
from amco.working import WorkingMemory
from types import SimpleNamespace


def test_greetings_skip_retrieval():
    analysis = ame.analyze_task("thanks!", WorkingMemory())
    assert analysis.kind == "chitchat"
    assert analysis.needs_retrieval is False
    assert analysis.limit == 0


def test_question_and_instruction_kinds():
    q = ame.analyze_task("What database does AMCO use?", WorkingMemory())
    assert q.kind == "question" and q.limit == ame.DEFAULT_DEPTH
    i = ame.analyze_task("Write a summary of the sprint report today", WorkingMemory())
    assert i.kind == "instruction"


def test_history_cues_deepen_retrieval():
    analysis = ame.analyze_task("What did we decide last time about storage?", WorkingMemory())
    assert analysis.wants_history is True
    assert analysis.limit == ame.DEEP_DEPTH


def test_thin_message_borrows_pinned_task():
    wm = WorkingMemory()
    wm.set_task("Write the sprint report")
    analysis = ame.analyze_task("ok so?", wm)
    assert analysis.kind == "followup"
    assert analysis.needs_retrieval is True
    assert "sprint report" in analysis.retrieval_query
    assert analysis.limit == ame.DEEP_DEPTH


def test_duplicate_candidates_are_dropped():
    a = {"id": 1, "category": "x", "content": "Uses SQLite."}
    b = {"id": 2, "category": "x", "content": "uses   sqlite"}
    kept, skipped = ame.resolve_duplicates([a, b])
    assert [m["id"] for m in kept] == [1]
    assert skipped == [{"id": 2, "reason": "duplicate of #1"}]


def test_conflict_prefers_higher_confidence_then_newer():
    a = {"id": 1, "content": "The API timeout for requests is 30 seconds",
         "confidence": 1.0, "updated_at": "2026-01-01 00:00:00"}
    b = {"id": 2, "content": "The API timeout for requests is 60 seconds",
         "confidence": 0.4, "updated_at": "2026-02-01 00:00:00"}
    assert ame.detect_conflicts([a, b]) == [(1, 2)]
    b["confidence"] = 1.0
    assert ame.detect_conflicts([a, b]) == [(2, 1)]


def test_unrelated_memories_do_not_conflict():
    a = {"id": 1, "content": "AMCO uses SQLite for storage", "confidence": 1.0, "updated_at": ""}
    b = {"id": 2, "content": "The garden needs watering", "confidence": 1.0, "updated_at": ""}
    assert ame.detect_conflicts([a, b]) == []


def test_budget_skips_without_truncating():
    small = {"id": 1, "category": "g", "content": "short"}
    big = {"id": 2, "category": "g", "content": "x" * 4000}
    selected, skipped = ame.select_within_budget([big, small], 100)
    assert selected == [small] and skipped == [big]


def test_prepare_drops_duplicate_memories(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    add_memory("The project codename is AMCO", db_path=db)
    add_memory("The project codename is AMCO", db_path=db)
    prepared = ame.prepare("What is the project codename?", WorkingMemory())
    assert len(prepared.memories) == 1
    assert prepared.report.skipped[0]["reason"].startswith("duplicate")


def test_prepare_ignores_superseded_memories(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    old = add_memory("Storage uses JSON files", db_path=db)
    new = add_memory("Storage uses SQLite", db_path=db, supersedes=old)
    prepared = ame.prepare("storage", WorkingMemory())
    assert [m["id"] for m in prepared.memories] == [new]


def test_prepare_adds_conflict_note_to_prompt(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    add_memory("The API timeout for requests is 30 seconds", db_path=db)
    add_memory("The API timeout for requests is 60 seconds", db_path=db)
    prepared = ame.prepare("What is the API timeout for requests?", WorkingMemory())
    assert prepared.report.conflicts
    assert "may disagree" in prepared.messages[0]["content"]


def test_report_is_stored_and_readable(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    add_memory("The project codename is AMCO", db_path=db)
    monkeypatch.setattr(engine, "get_model", lambda: SimpleNamespace(chat=lambda messages: "ok"))
    wm = WorkingMemory()
    engine.answer("What is the project codename?", wm)
    assert wm.last_report is not None
    text = "\n".join(wm.last_report.lines())
    assert "Selected: #1" in text
    assert "Memory tokens" in text
    wm.clear()
    assert wm.last_report is None