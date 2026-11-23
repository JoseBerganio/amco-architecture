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
from pathlib import Path

import pytest
from typer.testing import CliRunner

import amco.cli.common as common
from amco.cli import app
from amco.evaluation import (
    FixtureQuery,
    Observation,
    SavedRun,
    build_suite_result,
    collect_meta,
    load_run_file,
    save_run,
    score_query,
)

runner = CliRunner()

TINY = {
    "name": "tiny",
    "memories": [
        {"key": "db", "content": "The project database is SQLite"},
        {"key": "car", "content": "The company car is red"},
    ],
    "queries": [
        {"id": "q-db", "query": "What database does the project use?", "expect": ["db"],
         "tags": ["exact"], "split": "train"},
        {"id": "q-para", "query": "Which vehicle has a crimson colour?", "expect": ["car"],
         "tags": ["paraphrase"], "split": "dev"},
        {"id": "q-neg", "query": "What is the capital of Australia?",
         "tags": ["negative"], "split": "dev"},
    ],
}  # recall and MRR are both 0.5: the paraphrase query cannot match by words


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)
    # Rich fixes the width when a console is created; wide consoles keep assertions from wrapping.
    monkeypatch.setattr(common.console, "_width", 200)
    monkeypatch.setattr(common.err_console, "_width", 200)


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "AMCO_EVAL_DIR": str(tmp_path / "runs"),
        "AMCO_DB_PATH": str(tmp_path / "never.sqlite3"),
    }


def _fixture_file(tmp_path: Path) -> str:
    path = tmp_path / "tiny.json"
    path.write_text(json.dumps(TINY), encoding="utf-8")
    return str(path)


def _invoke(tmp_path: Path, *args: str):
    return runner.invoke(app, list(args), env=_env(tmp_path))


# --- eval run ------------------------------------------------------------------


def test_eval_group_lists_its_commands(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "--help")
    assert result.exit_code == 0
    for name in ("run", "compare", "list"):
        assert name in result.output


def test_run_prints_the_report_and_never_touches_the_memory_database(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path))
    assert result.exit_code == 0
    assert "Retrieval (k=5)" in result.output and "1/2 (50.0%)" in result.output
    assert not (tmp_path / "never.sqlite3").exists()
    assert not (tmp_path / "runs").exists()  # nothing saved unless asked


def test_save_note_list_and_the_existing_name_rules(tmp_path: Path):
    f = _fixture_file(tmp_path)
    first = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--save", "base", "--note", "abc123")
    assert first.exit_code == 0 and "Saved run 'base'" in first.output
    assert "Tip:" not in first.output
    saved = load_run_file(tmp_path / "runs" / "base.json")
    assert saved.meta.note == "abc123" and saved.suite.fixture_name == "tiny"

    listed = _invoke(tmp_path, "eval", "list")
    assert listed.exit_code == 0 and "base" in listed.output and "1/2 (50.0%)" in listed.output

    again = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--save", "base")
    assert again.exit_code == 1 and "already exists" in again.output
    assert "Retrieval" not in again.output  # refused before running

    forced = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--save", "base", "--overwrite")
    assert forced.exit_code == 0 and "Tip:" in forced.output  # no note this time


def test_a_bad_save_name_fails_before_running_and_writes_nothing(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path),
                     "--save", "../evil")
    assert result.exit_code == 1 and "Retrieval" not in result.output
    assert not (tmp_path / "runs").exists() and not (tmp_path / "evil.json").exists()


def test_out_writes_a_file_without_using_the_eval_folder(tmp_path: Path):
    target = tmp_path / "bench" / "b.json"
    result = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path),
                     "--out", str(target), "--note", "x")
    assert result.exit_code == 0 and target.is_file()
    assert not (tmp_path / "runs").exists()
    refused = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path),
                      "--out", str(target))
    assert refused.exit_code == 1 and "already exists" in refused.output


def test_json_output_is_pure_json(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path),
                     "--json", "--tag", "exact")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["suite"]["fixture_name"] == "tiny"
    assert data["meta"]["tags"] == ["exact"]
    assert [r["id"] for r in data["suite"]["results"]] == ["q-db"]


def test_tag_filter_and_unknown_tag(tmp_path: Path):
    f = _fixture_file(tmp_path)
    ok = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--tag", "exact")
    assert ok.exit_code == 0 and "tags: exact" in ok.output
    bad = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--tag", "exactt")
    assert bad.exit_code == 2 and "exactt" in bad.output


def test_verbose_lists_the_miss(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "run", "--fixtures", _fixture_file(tmp_path), "--verbose")
    assert "Queries needing attention: 1 of 3" in result.output and "q-para" in result.output


def test_broken_fixtures_give_a_clear_message_not_a_traceback(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    result = _invoke(tmp_path, "eval", "run", "--fixtures", str(bad))
    assert result.exit_code == 1 and "not valid JSON" in result.output
    assert "Traceback" not in result.output
    missing = _invoke(tmp_path, "eval", "run", "--fixtures", str(tmp_path / "nope.json"))
    assert missing.exit_code == 1 and "Cannot read" in missing.output


def test_gates_set_the_exit_code_and_the_run_is_still_saved(tmp_path: Path):
    f = _fixture_file(tmp_path)
    passing = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--min-recall", "0.5", "--min-mrr", "0.5")
    assert passing.exit_code == 0
    failing = _invoke(tmp_path, "eval", "run", "--fixtures", f, "--min-recall", "0.9", "--save", "gated")
    assert failing.exit_code == 1 and "below the required" in failing.output
    assert (tmp_path / "runs" / "gated.json").is_file()
    assert _invoke(tmp_path, "eval", "run", "--fixtures", f, "--min-recall", "1.5").exit_code == 2


def test_default_packaged_dataset_runs_from_the_cli(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "run")
    assert result.exit_code == 0
    assert "55 queries" in result.output and "Retrieval (k=5)" in result.output


# --- eval compare and list -----------------------------------------------------------


def _result(id, expect=(), selected=()):
    observation = Observation(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=tuple(selected), selected=tuple(selected), skipped=(), conflicts=(),
        memory_tokens=0, prompt_tokens=0, retrieval_ms=0.0, total_ms=0.0,
    )
    query = FixtureQuery(id=id, query=f"query {id}", expect=tuple(expect), tags=("exact",), split="train")
    return score_query(query, observation, 5)


def _run(results, digest="f" * 64) -> SavedRun:
    return SavedRun(collect_meta(), build_suite_result("fx", digest, 5, results))


GOOD = [_result("q1", ["a"], ["a"]), _result("q2", ["a"], ["a"])]
BAD = [_result("q1", ["a"], ["x"]), _result("q2", ["a"], ["x"])]


def _save(tmp_path: Path, name: str, run: SavedRun) -> None:
    save_run(name, run, tmp_path / "runs")


def test_compare_identical_runs_passes_the_check_even_with_the_same_name(tmp_path: Path):
    _save(tmp_path, "base", _run(GOOD))
    result = _invoke(tmp_path, "eval", "compare", "base", "base", "--check")
    assert result.exit_code == 0 and "No query changed status." in result.output
    assert "base (A)" in result.output and "base (B)" in result.output


def test_compare_check_fails_when_the_ship_rule_is_broken(tmp_path: Path):
    _save(tmp_path, "good", _run(GOOD))
    _save(tmp_path, "bad", _run(BAD))
    plain = _invoke(tmp_path, "eval", "compare", "good", "bad")
    assert plain.exit_code == 0 and "NOT met" in plain.output
    checked = _invoke(tmp_path, "eval", "compare", "good", "bad", "--check")
    assert checked.exit_code == 1 and "more than 1 net query" in checked.output


def test_compare_refuses_different_fixtures_unless_forced(tmp_path: Path):
    _save(tmp_path, "one", _run(GOOD, digest="a" * 64))
    _save(tmp_path, "two", _run(GOOD, digest="b" * 64))
    refused = _invoke(tmp_path, "eval", "compare", "one", "two")
    assert refused.exit_code == 1 and "different fixtures" in refused.output
    forced = _invoke(tmp_path, "eval", "compare", "one", "two", "--force")
    assert forced.exit_code == 0 and "Different fixtures" in forced.output
    unjudged = _invoke(tmp_path, "eval", "compare", "one", "two", "--force", "--check")
    assert unjudged.exit_code == 1 and "cannot be judged" in unjudged.output


def test_compare_accepts_file_paths_and_reports_unknown_names(tmp_path: Path):
    _save(tmp_path, "good", _run(GOOD))
    path = str(tmp_path / "runs" / "good.json")
    assert _invoke(tmp_path, "eval", "compare", path, path).exit_code == 0
    missing = _invoke(tmp_path, "eval", "compare", "good", "nope")
    assert missing.exit_code == 1 and "No saved run 'nope'" in missing.output


def test_list_with_nothing_saved(tmp_path: Path):
    result = _invoke(tmp_path, "eval", "list")
    assert result.exit_code == 0 and "No saved runs" in result.output