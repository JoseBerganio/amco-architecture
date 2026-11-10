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
import tomllib
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from amco.evaluation import (
    KNOWN_TAGS,
    FixtureError,
    fixture_hash,
    load_fixtures,
    parse_fixtures,
)
from amco.storage import extract_terms

REQUIRED_TAGS = {
    "exact", "stem", "multi-term", "paraphrase", "followup", "history",
    "superseded", "expired", "duplicate", "conflict", "negative", "chitchat",
}


def _data() -> dict:
    return {
        "name": "tiny",
        "memories": [
            {"key": "a", "content": "alpha fact"},
            {"key": "b", "content": "beta fact"},
        ],
        "queries": [{"id": "q1", "query": "alpha?", "expect": ["a"], "tags": ["exact"]}],
    }


# --- The packaged default dataset ------------------------------------------------


def test_default_dataset_is_packaged_and_declared():
    assert files("amco.evaluation").joinpath("datasets", "default.json").is_file()
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert "evaluation/datasets/*.json" in data["tool"]["setuptools"]["package-data"]["amco"]


def test_default_dataset_loads_with_the_planned_size_and_coverage():
    fixtures = load_fixtures()
    assert len(fixtures.memories) >= 25
    assert len(fixtures.queries) >= 40
    used = {tag for q in fixtures.queries for tag in q.tags}
    assert REQUIRED_TAGS <= used <= KNOWN_TAGS
    assert sum("paraphrase" in q.tags for q in fixtures.queries) >= 8


def test_default_dataset_has_a_train_dev_split_of_about_30_percent():
    queries = load_fixtures().queries
    assert all(q.split in ("train", "dev") for q in queries)
    share = sum(q.split == "dev" for q in queries) / len(queries)
    assert 0.2 <= share <= 0.4


def test_paraphrase_queries_share_no_terms_with_their_targets():
    """Guards against paraphrases that are secretly lexical (crude 5-letter stems)."""
    fixtures = load_fixtures()
    by_key = {m.key: m for m in fixtures.memories}

    def stems(text: str) -> set[str]:
        return {term[:5] for term in extract_terms(text)}

    for q in fixtures.queries:
        if "paraphrase" not in q.tags:
            continue
        for key in q.expect:
            shared = stems(q.query) & stems(by_key[key].content)
            assert not shared, f"{q.id} shares {shared} with {key}"


# --- Hash ------------------------------------------------------------------------


def test_hash_is_stable_and_ignores_name_and_description():
    fixtures = load_fixtures()
    digest = fixture_hash(fixtures)
    assert len(digest) == 64 and digest == fixture_hash(load_fixtures())
    assert fixture_hash(replace(fixtures, name="other", description="changed")) == digest


def test_hash_changes_when_a_memory_or_query_changes():
    fixtures = load_fixtures()
    digest = fixture_hash(fixtures)
    edited_memory = replace(fixtures.memories[0], content="something else")
    assert fixture_hash(replace(fixtures, memories=(edited_memory, *fixtures.memories[1:]))) != digest
    edited_query = replace(fixtures.queries[0], split="dev")
    assert fixture_hash(replace(fixtures, queries=(edited_query, *fixtures.queries[1:]))) != digest


# --- Parsing a valid set -----------------------------------------------------------


def test_minimal_set_gets_defaults():
    fixtures = parse_fixtures(_data())
    memory = fixtures.memories[0]
    assert (memory.category, memory.memory_type, memory.confidence) == ("general", "persistent", 1.0)
    assert (memory.age_days, memory.expires_in_days, memory.use_count) == (0, None, 0)
    query = fixtures.queries[0]
    assert query.forbid == () and query.turns == () and query.history is False


def test_values_are_stripped_and_turns_are_parsed():
    data = _data()
    data["memories"][0]["content"] = "  alpha fact  "
    data["queries"][0]["turns"] = [{"role": "user", "content": "hi there"}]
    fixtures = parse_fixtures(data)
    assert fixtures.memories[0].content == "alpha fact"
    assert fixtures.queries[0].turns[0].role == "user"


# --- Validation errors ---------------------------------------------------------------


def _mutate(fn):
    data = copy.deepcopy(_data())
    fn(data)
    return data


CASES = [
    ("duplicate key", lambda d: d["memories"].append({"key": "a", "content": "x"}), "duplicate key 'a'"),
    ("empty content", lambda d: d["memories"][0].update(content="   "), "cannot be empty"),
    ("bad key", lambda d: d["memories"][0].update(key="Bad Key"), "key must"),
    ("unknown memory field", lambda d: d["memories"][0].update(colour="red"), "unknown field"),
    ("bad memory type", lambda d: d["memories"][0].update(memory_type="working"), "memory_type"),
    ("negative age", lambda d: d["memories"][0].update(age_days=-1), "age_days"),
    ("bool age", lambda d: d["memories"][0].update(age_days=True), "age_days"),
    ("bad confidence", lambda d: d["memories"][0].update(confidence=2), "confidence"),
    ("supersedes unknown", lambda d: d["memories"][1].update(supersedes="zzz"), "unknown memory"),
    ("supersedes later", lambda d: d["memories"][0].update(supersedes="b"), "defined later"),
    ("supersedes self", lambda d: d["memories"][0].update(supersedes="a"), "itself"),
    ("expect unknown key", lambda d: d["queries"][0].update(expect=["zzz"]), "unknown memory 'zzz'"),
    ("expect and forbid", lambda d: d["queries"][0].update(forbid=["a"]), "both expect and forbid"),
    ("duplicate query id", lambda d: d["queries"].append(copy.deepcopy(d["queries"][0])), "duplicate id"),
    ("unknown tag", lambda d: d["queries"][0].update(tags=["exactt"]), "unknown tag"),
    ("no tags", lambda d: d["queries"][0].update(tags=[]), "at least one tag"),
    ("bad role", lambda d: d["queries"][0].update(turns=[{"role": "system", "content": "x"}]), "role"),
    ("bad expect_kind", lambda d: d["queries"][0].update(expect_kind="rant"), "expect_kind"),
    ("bad split", lambda d: d["queries"][0].update(split="test"), "split"),
    ("negative with expect", lambda d: d["queries"][0].update(tags=["negative"]), "'negative' but expects"),
    ("expects nothing", lambda d: d["queries"][0].update(expect=[]), "expects nothing"),
    ("expects expired", lambda d: d["memories"][0].update(expires_in_days=-1), "can never be retrieved"),
    ("empty memories", lambda d: d.update(memories=[]), "non-empty list"),
]


@pytest.mark.parametrize("label, change, message", CASES, ids=[c[0] for c in CASES])
def test_invalid_fixtures_are_rejected_with_a_clear_message(label, change, message):
    with pytest.raises(FixtureError, match=message):
        parse_fixtures(_mutate(change))


def test_expecting_a_superseded_memory_is_rejected():
    def change(d):
        d["memories"][1]["supersedes"] = "a"

    with pytest.raises(FixtureError, match="can never be retrieved"):
        parse_fixtures(_mutate(change))


def test_two_memories_cannot_supersede_the_same_one():
    def change(d):
        d["memories"].append({"key": "c", "content": "gamma fact", "supersedes": "a"})
        d["memories"][1]["supersedes"] = "a"
        d["queries"][0]["expect"] = ["b"]

    with pytest.raises(FixtureError, match="already superseded"):
        parse_fixtures(_mutate(change))


def test_top_level_must_be_an_object():
    with pytest.raises(FixtureError, match="expected an object"):
        parse_fixtures([])


def test_every_problem_is_reported_at_once():
    def change(d):
        d["memories"][0]["content"] = ""
        d["memories"][1]["confidence"] = 5

    with pytest.raises(FixtureError) as info:
        parse_fixtures(_mutate(change))
    text = str(info.value)
    assert "2 problem(s)" in text and "memories[0]" in text and "memories[1]" in text


# --- Loading files ---------------------------------------------------------------------


def test_load_from_a_path_including_a_bom(tmp_path: Path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps(_data()), encoding="utf-8-sig")
    assert load_fixtures(path).name == "tiny"


def test_missing_and_malformed_files_raise_fixture_errors(tmp_path: Path):
    with pytest.raises(FixtureError, match="Cannot read"):
        load_fixtures(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FixtureError, match="not valid JSON"):
        load_fixtures(bad)


def test_validation_errors_name_the_file(tmp_path: Path):
    data = _data()
    data["memories"][0]["content"] = ""
    path = tmp_path / "f.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FixtureError, match="f.json"):
        load_fixtures(path)