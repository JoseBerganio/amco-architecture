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

import amco.ame as ame
from amco.evaluation import (
    DEFAULT_K,
    Ratio,
    load_fixtures,
    parse_fixtures,
    run_suite,
    select_queries,
)
from amco.storage import list_memories


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    """Evaluation numbers depend on settings, so tests must not inherit yours."""
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _tiny():
    return parse_fixtures({
        "name": "tiny",
        "memories": [
            {"key": "db", "content": "The project database is SQLite", "age_days": 10, "use_count": 3},
            {"key": "garden", "content": "The garden needs watering on Sundays", "age_days": 400},
            {"key": "old", "content": "Reports are exported as CSV", "age_days": 90},
            {"key": "new", "content": "Reports are exported as JSON", "age_days": 1, "supersedes": "old"},
            {"key": "demo", "content": "The demo happens on Friday", "expires_in_days": -3},
        ],
        "queries": [
            {"id": "q-db", "query": "What database does the project use?", "expect": ["db"],
             "tags": ["exact"], "split": "train", "expect_kind": "question"},
            {"id": "q-new", "query": "What format are reports exported in?", "expect": ["new"],
             "forbid": ["old"], "tags": ["superseded"], "split": "dev"},
            {"id": "q-demo", "query": "When is the demo?", "forbid": ["demo"],
             "tags": ["expired"], "split": "train"},
            {"id": "q-neg", "query": "What is the capital of Australia?",
             "tags": ["negative"], "split": "dev"},
            {"id": "q-chat", "query": "thanks!", "tags": ["chitchat"],
             "expect_kind": "chitchat", "split": "train"},
            {"id": "q-follow", "query": "Is it fast?", "expect": ["db"], "tags": ["followup"],
             "expect_kind": "followup", "split": "train",
             "turns": [{"role": "user", "content": "What database does the project use?"},
                       {"role": "assistant", "content": "SQLite."}]},
            {"id": "q-task", "query": "Anything else?", "expect": ["db"], "tags": ["followup"],
             "expect_kind": "followup", "split": "dev", "task": "Check the project database"},
        ],
    })


def _by_id(suite):
    return {r.id: r for r in suite.results}


def test_default_k_matches_the_ame_default_depth():
    assert DEFAULT_K == ame.DEFAULT_DEPTH


def test_tiny_suite_produces_the_expected_numbers():
    suite = run_suite(_tiny())
    assert len(suite.results) == 7 and suite.k == 5 and suite.fixture_name == "tiny"
    o = suite.overall
    assert o.candidates.hits == Ratio(4, 4)
    assert o.selected.hits == Ratio(4, 4)
    assert o.false_inclusion == Ratio(0, 3)
    assert o.forbid_violations == Ratio(0, 2)
    assert o.classifier == Ratio(4, 4)
    assert o.history_labels == Ratio(7, 7)
    assert set(suite.by_tag) == {"exact", "superseded", "expired", "negative", "chitchat", "followup"}
    assert set(suite.by_split) == {"train", "dev"}


def test_followups_use_seeded_turns_and_the_pinned_task():
    results = _by_id(run_suite(_tiny()))
    follow = results["q-follow"].observation
    assert follow.borrowed and "database" in follow.search_text and follow.selected == ("db",)
    task = results["q-task"].observation
    assert task.borrowed and task.depth == ame.DEEP_DEPTH and task.selected == ("db",)


def test_superseded_and_expired_memories_never_come_back():
    results = _by_id(run_suite(_tiny()))
    assert results["q-new"].observation.selected == ("new",)
    assert results["q-demo"].observation.selected == ()
    assert results["q-chat"].observation.candidates == ()


def test_the_configured_database_is_never_created(tmp_path: Path, monkeypatch):
    configured = tmp_path / "configured.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(configured))
    run_suite(_tiny())
    assert not configured.exists()


def test_a_given_path_is_kept_and_usage_is_never_counted(tmp_path: Path):
    db = tmp_path / "kept.sqlite3"
    run_suite(_tiny(), db_path=db)
    by_content = {m["content"]: m for m in list_memories(db_path=db)}
    assert by_content["The project database is SQLite"]["use_count"] == 3  # fixture value, untouched
    with pytest.raises(ValueError, match="already contains data"):
        run_suite(_tiny(), db_path=db)


def test_runs_are_repeatable():
    def shape(suite):
        return [(r.id, r.observation.candidates, r.observation.selected) for r in suite.results]

    assert shape(run_suite(_tiny())) == shape(run_suite(_tiny()))


def test_tag_filter_limits_queries_but_not_memories():
    suite = run_suite(_tiny(), tags=["followup"])
    assert [r.id for r in suite.results] == ["q-follow", "q-task"]
    assert suite.overall.candidates.hits == Ratio(2, 2)  # still found "db", so memories were built
    assert select_queries(_tiny(), "exact")[0].id == "q-db"


def test_bad_tags_and_bad_k_are_rejected():
    with pytest.raises(ValueError, match="Unknown tag"):
        run_suite(_tiny(), tags=["exactt"])
    with pytest.raises(ValueError, match="No queries carry"):
        run_suite(_tiny(), tags=["stem"])
    with pytest.raises(ValueError, match="k must"):
        run_suite(_tiny(), k=0)


def test_default_dataset_runs_end_to_end():
    fixtures = load_fixtures()
    suite = run_suite(fixtures)
    assert len(suite.results) == len(fixtures.queries) == 55
    assert suite.fixture_name == "default" and len(suite.fixture_hash) == 64
    # Storage guarantee, independent of any label: hidden memories never surface.
    hidden = {"meeting-day-old", "export-csv", "demo-friday"}
    for r in suite.results:
        assert not hidden & set(r.observation.candidates)
        assert not hidden & set(r.observation.selected)