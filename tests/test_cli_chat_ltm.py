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

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import amco.cli.common as common
from amco.cli import app
from amco.storage import list_memories

runner = CliRunner()
SESSION_RE = re.compile(r"Session: ([0-9a-f]{8})")


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch):
    # Rich fixes the width when a console is created; a wide one keeps assertions from wrapping.
    monkeypatch.setattr(common.console, "_width", 200)
    monkeypatch.setattr(common.err_console, "_width", 200)


def _chat(tmp_path: Path, lines: list[str], **extra_env: str):
    env = {"AMCO_DB_PATH": str(tmp_path / "chat.sqlite3"), **extra_env}
    result = runner.invoke(app, ["chat"], input="\n".join(lines) + "\n/exit\n", env=env)
    assert result.exit_code == 0
    return result


def _saved(tmp_path: Path) -> list[dict]:
    return list_memories(db_path=tmp_path / "chat.sqlite3")


def test_status_shows_the_session_id(tmp_path: Path):
    result = _chat(tmp_path, ["/status"])
    assert SESSION_RE.search(result.output)


def test_clear_starts_a_new_session(tmp_path: Path):
    result = _chat(tmp_path, ["/status", "/clear", "/status"])
    before, after = SESSION_RE.findall(result.output)
    assert before != after
    assert "New session" in result.output


def test_remember_records_the_chat_source_and_session(tmp_path: Path):
    result = _chat(tmp_path, ["/status", "/remember AMCO uses SQLite"])
    session_id = SESSION_RE.search(result.output).group(1)
    (item,) = _saved(tmp_path)
    assert item["source"] == "chat" and item["source_session"] == session_id
    assert (item["kind"], item["memory_type"], item["category"]) == ("fact", "persistent", "chat")


def test_summary_saves_a_long_term_summary_with_session_and_period(tmp_path: Path):
    result = _chat(tmp_path, ["/status", "/summary We chose SQLite for storage this session"])
    session_id = SESSION_RE.search(result.output).group(1)
    assert "Saved summary" in result.output
    (item,) = _saved(tmp_path)
    assert (item["kind"], item["memory_type"]) == ("summary", "long_term")
    assert (item["source"], item["category"]) == ("chat", "session")
    assert item["source_session"] == session_id
    assert item["period_start"] and item["period_end"]
    assert item["period_start"] <= item["period_end"]
    assert item["content"] == "We chose SQLite for storage this session"


def test_summary_without_text_shows_usage_and_saves_nothing(tmp_path: Path):
    result = _chat(tmp_path, ["/summary"])
    assert "Usage: /summary" in result.output
    assert _saved(tmp_path) == []


def test_a_summary_above_the_size_limit_is_refused(tmp_path: Path):
    # AMCO_MEMORY_TOKENS=100 gives a limit of 50 tokens (about 200 characters).
    result = _chat(tmp_path, ["/summary " + "word " * 80], AMCO_MEMORY_TOKENS="100")
    assert "too long" in result.output
    assert _saved(tmp_path) == []


def test_an_identical_summary_is_not_saved_twice(tmp_path: Path):
    result = _chat(tmp_path, ["/summary We chose SQLite", "/summary we chose sqlite."])
    assert "Already remembered" in result.output
    assert len(_saved(tmp_path)) == 1


def test_help_lists_the_summary_command(tmp_path: Path):
    assert "/summary" in _chat(tmp_path, ["/help"]).output