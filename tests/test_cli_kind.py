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
from pathlib import Path

import pytest
from typer.testing import CliRunner

import amco.cli.common as common
from amco.cli import app
from amco.storage import add_memory, get_memory, list_memories

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(common.console, "_width", 200)
    monkeypatch.setattr(common.err_console, "_width", 200)


def _run(tmp_path: Path, *args: str, **extra_env: str):
    env = {"AMCO_DB_PATH": str(tmp_path / "cli.sqlite3"), **extra_env}
    return runner.invoke(app, list(args), env=env)


def _db(tmp_path: Path) -> Path:
    return tmp_path / "cli.sqlite3"


# --- add: kind and the tier default (K8) -------------------------------------------


def test_a_plain_add_is_still_a_persistent_fact(tmp_path: Path):
    assert _run(tmp_path, "memory", "add", "A plain note").exit_code == 0
    item = get_memory(1, db_path=_db(tmp_path))
    assert (item["kind"], item["memory_type"]) == ("fact", "persistent")


def test_a_summary_defaults_to_long_term(tmp_path: Path):
    assert _run(tmp_path, "memory", "add", "Recap of the week", "--kind", "summary").exit_code == 0
    item = get_memory(1, db_path=_db(tmp_path))
    assert (item["kind"], item["memory_type"]) == ("summary", "long_term")


def test_an_explicit_type_beats_the_kind_default(tmp_path: Path):
    result = _run(tmp_path, "memory", "add", "Recap", "-k", "summary", "--type", "persistent")
    assert result.exit_code == 0
    assert get_memory(1, db_path=_db(tmp_path))["memory_type"] == "persistent"


def test_an_unknown_kind_is_rejected_and_nothing_is_saved(tmp_path: Path):
    assert _run(tmp_path, "memory", "add", "x note", "--kind", "diary").exit_code != 0
    assert list_memories(db_path=_db(tmp_path)) == []


def test_an_oversize_summary_is_refused_like_in_chat(tmp_path: Path):
    result = _run(tmp_path, "memory", "add", "word " * 80, "--kind", "summary", AMCO_MEMORY_TOKENS="100")
    assert result.exit_code != 0
    assert list_memories(db_path=_db(tmp_path)) == []


def test_an_oversize_fact_is_still_allowed(tmp_path: Path):
    # Known gap (S18-04): only summaries have a size check so far.
    result = _run(tmp_path, "memory", "add", "word " * 80, AMCO_MEMORY_TOKENS="100")
    assert result.exit_code == 0


# --- list ------------------------------------------------------------------------------


def test_list_shows_a_kind_column_and_filters_by_kind(tmp_path: Path):
    _run(tmp_path, "memory", "add", "alpha fact")
    _run(tmp_path, "memory", "add", "beta recap", "--kind", "summary")

    everything = _run(tmp_path, "memory", "list")
    assert "Kind" in everything.output and "alpha" in everything.output and "beta" in everything.output

    only = _run(tmp_path, "memory", "list", "--kind", "summary")
    assert "beta" in only.output and "alpha" not in only.output


def test_list_rejects_an_unknown_kind(tmp_path: Path):
    assert _run(tmp_path, "memory", "list", "--kind", "diary").exit_code != 0


# --- update and inspect ------------------------------------------------------------------


def test_update_changes_the_kind(tmp_path: Path):
    _run(tmp_path, "memory", "add", "a log entry")
    assert _run(tmp_path, "memory", "update", "1", "--kind", "record").exit_code == 0
    assert get_memory(1, db_path=_db(tmp_path))["kind"] == "record"
    assert "record" in _run(tmp_path, "memory", "inspect", "1").output


def test_update_rejects_an_unknown_kind(tmp_path: Path):
    _run(tmp_path, "memory", "add", "a note")
    assert _run(tmp_path, "memory", "update", "1", "-k", "diary").exit_code != 0
    assert get_memory(1, db_path=_db(tmp_path))["kind"] == "fact"


def test_inspect_shows_kind_session_and_period(tmp_path: Path):
    add_memory(
        "Recap of the week", kind="summary", source="chat", source_session="abc12345",
        period_start="2026-11-19 09:00:00", period_end="2026-11-19 10:00:00",
        db_path=_db(tmp_path),
    )
    out = _run(tmp_path, "memory", "inspect", "1").output
    assert "Kind:" in out and "summary" in out
    assert "abc12345" in out
    assert "2026-11-19 09:00:00 to 2026-11-19 10:00:00" in out


def test_inspect_shows_none_for_a_memory_without_session_or_period(tmp_path: Path):
    _run(tmp_path, "memory", "add", "a plain note")
    out = _run(tmp_path, "memory", "inspect", "1").output
    assert "Session:" in out and "Period:" in out and "(none)" in out