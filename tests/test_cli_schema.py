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

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from amco.cli import app
from amco.storage import SCHEMA_VERSION, SchemaError, add_memory

runner = CliRunner()

DATABASE_COMMANDS = [
    ["init"],
    ["memory", "add", "a note"],
    ["memory", "list"],
    ["memory", "inspect", "1"],
    ["memory", "update", "1", "--content", "x"],
    ["memory", "supersede", "1", "2"],
    ["memory", "restore", "1"],
    ["memory", "review"],
    ["memory", "search", "note"],
    ["memory", "reindex"],
    ["memory", "delete", "1", "--yes"],
]


def _newer_database(tmp_path: Path) -> dict[str, str]:
    db = tmp_path / "newer.sqlite3"
    add_memory("a note", db_path=db)
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()
    return {"AMCO_DB_PATH": str(db)}


@pytest.mark.parametrize("args", DATABASE_COMMANDS, ids=lambda a: " ".join(a))
def test_every_database_command_reports_a_newer_database_cleanly(tmp_path: Path, args):
    result = runner.invoke(app, args, env=_newer_database(tmp_path))
    assert result.exit_code == 1
    assert "newer" in result.output
    assert not isinstance(result.exception, SchemaError)


def test_chat_reports_a_newer_database_and_keeps_running(tmp_path: Path):
    result = runner.invoke(
        app,
        ["chat"],
        input="/remember something\nWhat is the project codename?\n/exit\n",
        env=_newer_database(tmp_path),
    )
    assert result.exit_code == 0
    assert result.output.count("Database error") == 2
    assert "Traceback" not in result.output
    assert "Goodbye." in result.output