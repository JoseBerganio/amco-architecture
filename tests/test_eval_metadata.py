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

import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest

import amco.ame as ame
import amco.config as config
from amco.evaluation import collect_meta


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def test_defaults_come_from_the_configuration_and_the_ame():
    meta = collect_meta()
    assert meta.mode == "fts" and meta.tags == () and meta.amco_variables == ()
    assert meta.ranking_weights == {
        "relevance": config.DEFAULT_WEIGHT_RELEVANCE,
        "confidence": config.DEFAULT_WEIGHT_CONFIDENCE,
        "freshness": config.DEFAULT_WEIGHT_FRESHNESS,
        "usefulness": config.DEFAULT_WEIGHT_USEFULNESS,
    }
    assert meta.half_life_days == config.DEFAULT_FRESHNESS_HALF_LIFE_DAYS
    assert meta.context == {
        "limit": config.DEFAULT_CONTEXT_TOKENS,
        "reserved_output": config.DEFAULT_RESERVED_OUTPUT_TOKENS,
        "memory_cap": config.DEFAULT_MEMORY_TOKENS,
    }
    assert meta.followup == {
        "min_terms": config.DEFAULT_FOLLOWUP_MIN_TERMS,
        "turns": config.DEFAULT_FOLLOWUP_TURNS,
    }
    assert meta.retrieval == {
        "default_depth": ame.DEFAULT_DEPTH,
        "deep_depth": ame.DEEP_DEPTH,
        "extra_candidates": ame.EXTRA_CANDIDATES,
    }
    assert isinstance(meta.fts5, bool)
    assert meta.sqlite_version and meta.python and meta.platform and meta.amco_version


def test_settings_changes_are_recorded(monkeypatch):
    monkeypatch.setenv("AMCO_CONTEXT_TOKENS", "2048")
    monkeypatch.setenv("AMCO_WEIGHT_RELEVANCE", "0.9")
    monkeypatch.setenv("AMCO_FOLLOWUP_MIN_TERMS", "4")
    monkeypatch.setenv("AMCO_FRESHNESS_HALF_LIFE_DAYS", "30")
    meta = collect_meta()
    assert meta.context["limit"] == 2048
    assert meta.ranking_weights["relevance"] == 0.9
    assert meta.followup["min_terms"] == 4
    assert meta.half_life_days == 30.0
    assert meta.amco_variables == tuple(sorted(
        ["AMCO_CONTEXT_TOKENS", "AMCO_WEIGHT_RELEVANCE",
         "AMCO_FOLLOWUP_MIN_TERMS", "AMCO_FRESHNESS_HALF_LIFE_DAYS"]
    ))


def test_values_of_unrelated_settings_are_never_recorded(monkeypatch):
    monkeypatch.setenv("AMCO_DB_PATH", "/very/private/place.sqlite3")
    meta = collect_meta()
    assert meta.amco_variables == ("AMCO_DB_PATH",)
    assert "private" not in json.dumps(asdict(meta))


def test_created_at_is_utc_and_a_naive_time_is_taken_as_utc():
    manila = timezone(timedelta(hours=8))
    assert collect_meta(now=datetime(2026, 11, 13, 9, 30, tzinfo=manila)).created_at == "2026-11-13T01:30:00Z"
    assert collect_meta(now=datetime(2026, 11, 13, 9, 30)).created_at == "2026-11-13T09:30:00Z"


def test_tags_are_sorted_and_a_single_tag_string_is_accepted():
    assert collect_meta(tags=["stem", "exact"]).tags == ("exact", "stem")
    assert collect_meta(tags="exact").tags == ("exact",)
    assert collect_meta(note="trial").note == "trial"


def test_meta_is_json_safe():
    json.dumps(asdict(collect_meta()))