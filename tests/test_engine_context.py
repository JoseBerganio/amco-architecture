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

import pytest

import amco.engine as engine
from amco.working import WorkingMemory, estimate_tokens


def _capture(monkeypatch):
    seen = {}

    def fake_chat(messages):
        seen["messages"] = messages
        return "ok"

    monkeypatch.setattr(engine, "ollama_chat", fake_chat)
    return seen


def test_history_is_sent_and_recorded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "t.sqlite3"))
    seen = _capture(monkeypatch)
    wm = WorkingMemory()
    engine.answer("first question", wm)
    engine.answer("second question", wm)

    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert seen["messages"][1]["content"] == "first question"
    assert seen["messages"][-1]["content"] == "second question"
    assert len(wm.turns) == 4


def test_failed_model_call_does_not_record_turns(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "t.sqlite3"))

    def boom(messages):
        raise RuntimeError("Ollama is down")

    monkeypatch.setattr(engine, "ollama_chat", boom)
    wm = WorkingMemory()
    with pytest.raises(RuntimeError):
        engine.answer("hello", wm)
    assert wm.turns == []


def test_task_appears_in_system_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "t.sqlite3"))
    seen = _capture(monkeypatch)
    wm = WorkingMemory()
    wm.set_task("Write the sprint report")
    engine.answer("hi there", wm)
    assert "Write the sprint report" in seen["messages"][0]["content"]


def test_history_is_trimmed_to_fit_the_context_budget(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "t.sqlite3"))
    monkeypatch.setenv("AMCO_CONTEXT_TOKENS", "300")
    monkeypatch.setenv("AMCO_RESERVED_OUTPUT_TOKENS", "50")
    seen = _capture(monkeypatch)

    wm = WorkingMemory()
    for i in range(10):
        wm.add("user", f"question number {i:02d} " + "x" * 22)
        wm.add("assistant", f"answer number {i:02d} " + "y" * 24)

    engine.answer("latest question", wm)

    sent = sum(estimate_tokens(m["content"]) for m in seen["messages"])
    assert sent <= 300 - 50
    assert wm.dropped_turns > 0
    assert seen["messages"][-1]["content"] == "latest question"
    assert seen["messages"][1]["role"] == "user"  # history starts on a user turn


def test_select_memories_skips_oversize_without_truncating():
    small = {"id": 1, "category": "general", "content": "short"}
    big = {"id": 2, "category": "general", "content": "x" * 4000}
    chosen = engine.select_memories([big, small], budget_tokens=100)
    assert chosen == [small]