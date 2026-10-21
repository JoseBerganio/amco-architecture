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
import amco.ranking as ranking
import amco.storage as storage

WEIGHT_VARS = (
    "AMCO_WEIGHT_RELEVANCE", "AMCO_WEIGHT_CONFIDENCE",
    "AMCO_WEIGHT_FRESHNESS", "AMCO_WEIGHT_USEFULNESS",
)


def test_default_database_location():
    assert config.DEFAULT_DB == Path.home() / ".amco" / "amco.sqlite3"


def test_database_path_is_read_at_call_time(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AMCO_DB_PATH", raising=False)
    assert config.database_path() == config.DEFAULT_DB
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "a.sqlite3"))
    assert config.database_path() == tmp_path / "a.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "b.sqlite3"))
    assert config.database_path() == tmp_path / "b.sqlite3"


def test_storage_re_exports_the_config_objects():
    assert storage.DEFAULT_DB is config.DEFAULT_DB
    assert storage.database_path is config.database_path


def test_timeout_seconds(monkeypatch):
    monkeypatch.delenv("AMCO_TIMEOUT_SECONDS", raising=False)
    assert config.timeout_seconds() == 300.0
    monkeypatch.setenv("AMCO_TIMEOUT_SECONDS", "12")
    assert config.timeout_seconds() == 12.0
    monkeypatch.setenv("AMCO_TIMEOUT_SECONDS", "zero")
    assert config.timeout_seconds() == 300.0


def test_provider_name(monkeypatch):
    monkeypatch.delenv("AMCO_PROVIDER", raising=False)
    assert config.provider_name() == "ollama"
    monkeypatch.setenv("AMCO_PROVIDER", "  OLLAMA ")
    assert config.provider_name() == "ollama"
    monkeypatch.setenv("AMCO_PROVIDER", "")
    assert config.provider_name() == "ollama"
    monkeypatch.setenv("AMCO_PROVIDER", "other")
    assert config.provider_name() == "other"


def test_ranking_weight_settings_defaults_and_bad_values(monkeypatch):
    for name in WEIGHT_VARS:
        monkeypatch.delenv(name, raising=False)
    assert config.ranking_weight_settings() == (0.65, 0.15, 0.05, 0.15)
    monkeypatch.setenv("AMCO_WEIGHT_RELEVANCE", "0.9")
    monkeypatch.setenv("AMCO_WEIGHT_CONFIDENCE", "abc")
    monkeypatch.setenv("AMCO_WEIGHT_FRESHNESS", "-1")
    assert config.ranking_weight_settings() == (0.9, 0.15, 0.05, 0.15)


def test_ranking_defaults_come_from_config():
    defaults = ranking.RankingWeights()
    assert (
        defaults.relevance,
        defaults.confidence,
        defaults.freshness,
        defaults.usefulness,
    ) == (
        config.DEFAULT_WEIGHT_RELEVANCE,
        config.DEFAULT_WEIGHT_CONFIDENCE,
        config.DEFAULT_WEIGHT_FRESHNESS,
        config.DEFAULT_WEIGHT_USEFULNESS,
    )


def test_weights_from_env_still_works(monkeypatch):
    for name in WEIGHT_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AMCO_WEIGHT_USEFULNESS", "0.3")
    assert ranking.weights_from_env().usefulness == 0.3


def test_only_config_reads_the_environment():
    package = Path(config.__file__).parent
    offenders = []
    for path in package.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "os.getenv" in text or "os.environ" in text:
            offenders.append(str(path.relative_to(package)))
    assert offenders == []