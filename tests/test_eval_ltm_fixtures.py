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

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from amco.evaluation import (
    KNOWN_TAGS,
    FixtureError,
    build_database,
    canonical_json,
    fixture_hash,
    parse_fixtures,
)
from amco.storage import get_memory

NOW = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)


def _data() -> dict:
    return {
        "name": "ltm-tiny",
        "memories": [
            {"key": "fact", "content": "alpha fact"},
            {"key": "recap", "content": "beta recap", "category": "session",
             "memory_type": "long_term", "kind": "summary", "period_age_days": 10},
        ],
        "queries": [
            {"id": "q1", "query": "beta?", "expect": ["recap"], "tags": ["ltm"], "history": True},
        ],
    }


def test_ltm_is_a_known_tag():
    assert "ltm" in KNOWN_TAGS


def test_kind_and_period_are_parsed_with_defaults():
    fixtures = parse_fixtures(_data())
    fact, recap = fixtures.memories
    assert (fact.kind, fact.period_age_days) == ("fact", None)
    assert (recap.kind, recap.period_age_days) == ("summary", 10)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda d: d["memories"][0].update(kind="diary"), "kind"),
        (lambda d: d["memories"][1].update(period_age_days=-1), "period_age_days"),
        (lambda d: d["memories"][1].update(period_age_days=True), "period_age_days"),
    ],
)
def test_bad_kind_and_period_are_rejected(change, message):
    data = copy.deepcopy(_data())
    change(data)
    with pytest.raises(FixtureError, match=message):
        parse_fixtures(data)


def test_new_optional_fields_are_left_out_of_the_hash_while_at_their_default():
    plain = _data()
    plain["memories"][1].pop("kind")
    plain["memories"][1].pop("period_age_days")
    text = canonical_json(parse_fixtures(plain))
    assert '"kind"' not in text and '"period_age_days"' not in text


def test_a_used_kind_or_period_changes_the_hash_and_appears_in_the_canonical_form():
    with_kind = parse_fixtures(_data())
    text = canonical_json(with_kind)
    assert '"kind":"summary"' in text and '"period_age_days":10' in text
    plain = _data()
    plain["memories"][1].pop("kind")
    plain["memories"][1].pop("period_age_days")
    assert fixture_hash(parse_fixtures(plain)) != fixture_hash(with_kind)


def test_the_builder_stores_kind_tier_and_a_relative_period(tmp_path: Path):
    db = tmp_path / "e.sqlite3"
    ids = build_database(parse_fixtures(_data()), db, now=NOW)
    fact = get_memory(ids["fact"], db_path=db)
    recap = get_memory(ids["recap"], db_path=db)
    assert (fact["kind"], fact["period_start"]) == ("fact", None)
    assert (recap["kind"], recap["memory_type"]) == ("summary", "long_term")
    assert recap["period_start"] == recap["period_end"] == "2026-11-02"