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

import amco.config as config


def test_eval_dir_defaults_to_an_eval_folder_next_to_the_database(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AMCO_EVAL_DIR", raising=False)
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "data" / "a.sqlite3"))
    assert config.eval_dir() == tmp_path / "data" / "eval"


def test_eval_dir_follows_the_database_at_call_time(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AMCO_EVAL_DIR", raising=False)
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "one" / "a.sqlite3"))
    assert config.eval_dir() == tmp_path / "one" / "eval"
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "two" / "a.sqlite3"))
    assert config.eval_dir() == tmp_path / "two" / "eval"


def test_eval_dir_can_be_overridden_and_expands_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AMCO_EVAL_DIR", str(tmp_path / "runs"))
    assert config.eval_dir() == tmp_path / "runs"
    monkeypatch.setenv("AMCO_EVAL_DIR", "~/amco-runs")
    assert config.eval_dir() == Path("~/amco-runs").expanduser()


def test_set_amco_variables_lists_names_only(monkeypatch):
    monkeypatch.setenv("AMCO_ZZ_TEST", "secret-value")
    names = config.set_amco_variables()
    assert "AMCO_ZZ_TEST" in names
    assert list(names) == sorted(names)
    assert all(name.startswith("AMCO_") for name in names)
    assert not any("secret-value" in name for name in names)