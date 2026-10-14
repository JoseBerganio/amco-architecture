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

from amco.storage import add_memory
import amco.engine as engine


def test_answer_passes_retrieved_memories_to_model(tmp_path: Path, monkeypatch):
    db = tmp_path / "test.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    add_memory("The project codename is AMCO", db_path=db)

    seen = {}
    def fake_chat(messages):
        seen["messages"] = messages
        return "The project codename is AMCO."

    monkeypatch.setattr(engine, "ollama_chat", fake_chat)
    response, used = engine.answer("What is the project codename?")
    assert response == "The project codename is AMCO."
    assert len(used) == 1
    assert "The project codename is AMCO" in seen["messages"][0]["content"]
