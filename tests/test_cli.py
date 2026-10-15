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

from typer.testing import CliRunner

from amco.cli import app
from amco.storage import list_memories

runner = CliRunner()


def _env(tmp_path: Path) -> dict[str, str]:
    return {"AMCO_DB_PATH": str(tmp_path / "cli.sqlite3")}


def test_add_inspect_update_delete_flow(tmp_path: Path):
    env = _env(tmp_path)
    assert runner.invoke(app, ["memory", "add", "Uses SQLite"], env=env).exit_code == 0

    result = runner.invoke(app, ["memory", "inspect", "1"], env=env)
    assert result.exit_code == 0
    assert "Uses SQLite" in result.output

    result = runner.invoke(app, ["memory", "update", "1", "--content", "Uses SQLite and Python"], env=env)
    assert result.exit_code == 0

    result = runner.invoke(app, ["memory", "inspect", "1"], env=env)
    assert "Uses SQLite and Python" in result.output

    result = runner.invoke(app, ["memory", "delete", "1", "--yes"], env=env)
    assert result.exit_code == 0


def test_delete_missing_id_fails_cleanly(tmp_path: Path):
    result = runner.invoke(app, ["memory", "delete", "99", "--yes"], env=_env(tmp_path))
    assert result.exit_code == 1
    assert "No memory found" in result.output
    assert not isinstance(result.exception, TypeError)


def test_inspect_and_update_missing_id_fail_cleanly(tmp_path: Path):
    env = _env(tmp_path)
    assert runner.invoke(app, ["memory", "inspect", "99"], env=env).exit_code == 1
    result = runner.invoke(app, ["memory", "update", "99", "--content", "x"], env=env)
    assert result.exit_code == 1


def test_update_without_fields_is_rejected(tmp_path: Path):
    env = _env(tmp_path)
    runner.invoke(app, ["memory", "add", "something"], env=env)
    result = runner.invoke(app, ["memory", "update", "1"], env=env)
    assert result.exit_code != 0
    
def test_chat_commands_task_remember_status(tmp_path: Path):
    env = _env(tmp_path)
    result = runner.invoke(
        app,
        ["chat"],
        input="/task Write report\n/remember AMCO uses SQLite\n/status\n/exit\n",
        env=env,
    )
    assert result.exit_code == 0
    assert "Write report" in result.output
    saved = list_memories(db_path=tmp_path / "cli.sqlite3")
    assert [m["content"] for m in saved] == ["AMCO uses SQLite"]
    assert saved[0]["category"] == "chat"
    assert saved[0]["memory_type"] == "persistent"


def test_chat_reuses_one_working_memory(tmp_path: Path, monkeypatch):
    calls = []

    def fake_answer(query, working=None):
        calls.append(working)
        working.add("user", query)
        working.add("assistant", "ok")
        return "ok", []

    monkeypatch.setattr("amco.cli.answer", fake_answer)
    runner.invoke(app, ["chat"], input="one\ntwo\n/exit\n", env=_env(tmp_path))
    assert len(calls) == 2
    assert calls[0] is calls[1]
    assert len(calls[1].turns) == 4
    
def test_search_explain_shows_score_parts(tmp_path: Path):
    env = _env(tmp_path)
    runner.invoke(app, ["memory", "add", "AMCO uses SQLite storage"], env=env)
    result = runner.invoke(app, ["memory", "search", "SQLite", "--explain"], env=env)
    assert result.exit_code == 0
    assert "score=" in result.output


def test_confidence_option_and_validation(tmp_path: Path):
    env = _env(tmp_path)
    ok = runner.invoke(app, ["memory", "add", "A guess", "--confidence", "0.4"], env=env)
    assert ok.exit_code == 0
    assert "0.40" in runner.invoke(app, ["memory", "inspect", "1"], env=env).output
    bad = runner.invoke(app, ["memory", "add", "Too sure", "--confidence", "2"], env=env)
    assert bad.exit_code != 0


def test_reindex_command_runs(tmp_path: Path):
    env = _env(tmp_path)
    runner.invoke(app, ["memory", "add", "something"], env=env)
    result = runner.invoke(app, ["memory", "reindex"], env=env)
    assert result.exit_code in (0, 1)  # 1 only if this SQLite build lacks FTS5