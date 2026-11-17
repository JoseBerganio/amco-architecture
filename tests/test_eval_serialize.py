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
import json
import os

import pytest

from amco.evaluation import (
    RunError,
    SavedRun,
    collect_meta,
    dumps_run,
    loads_run,
    parse_fixtures,
    run_suite,
)
from amco.evaluation.serialize import FORMAT_VERSION, run_from_payload, run_to_payload


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _real_run() -> SavedRun:
    fixtures = parse_fixtures({
        "name": "tiny",
        "memories": [
            {"key": "db", "content": "The project database is SQLite", "age_days": 10},
            {"key": "old", "content": "Reports are exported as CSV", "age_days": 90},
            {"key": "new", "content": "Reports are exported as JSON", "age_days": 1, "supersedes": "old"},
        ],
        "queries": [
            {"id": "q-db", "query": "What database does the project use?", "expect": ["db"],
             "tags": ["exact"], "split": "train", "expect_kind": "question"},
            {"id": "q-new", "query": "What format are reports exported in?", "expect": ["new"],
             "forbid": ["old"], "tags": ["superseded"], "split": "dev"},
            {"id": "q-neg", "query": "What is the capital of Australia?",
             "tags": ["negative"], "split": "dev"},
        ],
    })
    return SavedRun(collect_meta(note="test"), run_suite(fixtures))


def test_a_real_run_survives_a_round_trip_exactly():
    run = _real_run()
    assert loads_run(dumps_run(run)) == run


def test_output_is_json_with_a_version_a_headline_and_one_trailing_newline():
    text = dumps_run(_real_run())
    assert text.endswith("}\n") and not text.endswith("\n\n") and "\r" not in text
    data = json.loads(text)
    assert data["format_version"] == FORMAT_VERSION
    assert data["headline"]["selected_hits"].startswith("2/2")
    assert len(data["suite"]["results"]) == 3


def test_headline_is_informational_and_ignored_on_load():
    run = _real_run()
    payload = run_to_payload(run)
    payload["headline"]["selected_hits"] = "0/99 (bogus)"
    assert run_from_payload(payload) == run


def test_summaries_are_recomputed_not_stored():
    payload = run_to_payload(_real_run())
    assert "overall" not in payload["suite"] and "by_tag" not in payload["suite"]


def _payload() -> dict:
    return copy.deepcopy(run_to_payload(_real_run()))


def test_a_newer_format_is_refused_with_a_clear_message():
    payload = _payload()
    payload["format_version"] = FORMAT_VERSION + 1
    with pytest.raises(RunError, match="newer"):
        run_from_payload(payload)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda p: p.pop("format_version"), "format_version"),
        (lambda p: p.update(format_version="1"), "format_version"),
        (lambda p: p.update(format_version=0), "unsupported"),
        (lambda p: p["suite"].update(results="nope"), "malformed"),
        (lambda p: p["suite"]["results"][0].pop("observation"), "malformed"),
        (lambda p: p["suite"].pop("k"), "malformed"),
        (lambda p: p.pop("meta"), "malformed"),
        (lambda p: p["meta"].update(ranking_weights=[1, 2]), "malformed"),
    ],
)
def test_damaged_payloads_raise_run_errors_not_key_errors(change, message):
    payload = _payload()
    change(payload)
    with pytest.raises(RunError, match=message):
        run_from_payload(payload)


def test_bad_json_and_non_objects_are_rejected():
    with pytest.raises(RunError, match="not valid JSON"):
        loads_run("not json")
    with pytest.raises(RunError, match="expected a JSON object"):
        loads_run("[]")