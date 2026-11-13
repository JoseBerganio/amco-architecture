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

from amco.evaluation import (
    FixtureQuery,
    Observation,
    RunError,
    SavedRun,
    build_suite_result,
    check_name,
    collect_meta,
    list_runs,
    load_run,
    load_run_file,
    save_run,
    saved_names,
    score_query,
    write_run_file,
)


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _result(id, expect=(), selected=()):
    observation = Observation(
        kind="question", wants_history=False, borrowed=False, depth=5, search_text="q",
        candidates=tuple(selected), selected=tuple(selected), skipped=(), conflicts=(),
        memory_tokens=10, prompt_tokens=100, retrieval_ms=1.0, total_ms=2.0,
    )
    query = FixtureQuery(id=id, query=f"query {id}", expect=tuple(expect), tags=("exact",), split="train")
    return score_query(query, observation, 5)


def _run() -> SavedRun:
    results = [_result("q1", ["a"], ["a"]), _result("q2", ["a"], ["x"])]
    return SavedRun(collect_meta(), build_suite_result("fx", "f" * 64, 5, results))


# --- Names ------------------------------------------------------------------------


def test_check_name_accepts_and_rejects():
    for good in ("baseline", "fts-baseline-0.6", "a", "Run_1.2", "x" * 64):
        assert check_name(good) == good
    for bad in ("", ".hidden", "..", "-x", "a b", "a/b", "a\\b", "x" * 65, "run.json", "RUN.JSON", "é"):
        with pytest.raises(RunError):
            check_name(bad)


def test_a_traversal_name_is_rejected_and_nothing_is_written(tmp_path: Path):
    with pytest.raises(RunError):
        save_run("../evil", _run(), tmp_path / "runs")
    assert not (tmp_path / "evil.json").exists()


# --- Saving and loading ---------------------------------------------------------------


def test_save_then_load_by_name(tmp_path: Path):
    run = _run()
    path = save_run("base", run, tmp_path)
    assert path == tmp_path / "base.json"
    assert load_run("base", tmp_path) == run
    assert load_run_file(path) == run


def test_an_existing_name_is_refused_unless_overwrite_is_set(tmp_path: Path):
    save_run("base", _run(), tmp_path)
    with pytest.raises(RunError, match="already exists"):
        save_run("base", _run(), tmp_path)
    save_run("base", _run(), tmp_path, overwrite=True)


def test_write_run_file_creates_folders_and_leaves_no_temp_files(tmp_path: Path):
    target = tmp_path / "benchmarks" / "nested" / "b.json"
    write_run_file(target, _run())
    assert [p.name for p in target.parent.iterdir()] == ["b.json"]
    assert b"\r" not in target.read_bytes()


def test_a_failed_write_keeps_the_old_file_and_cleans_up(tmp_path: Path, monkeypatch):
    path = save_run("base", _run(), tmp_path)
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk on fire")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RunError, match="Cannot write"):
        save_run("base", _run(), tmp_path, overwrite=True)
    monkeypatch.undo()
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["base.json"]


def test_default_folder_comes_from_the_configuration(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AMCO_EVAL_DIR", str(tmp_path / "runs"))
    path = save_run("base", _run())
    assert path == tmp_path / "runs" / "base.json"
    assert load_run("base") == _run() or load_run("base").suite.fixture_name == "fx"


def test_a_path_can_be_used_instead_of_a_name(tmp_path: Path):
    written = write_run_file(tmp_path / "somewhere" / "b.json", _run())
    assert load_run(str(written), tmp_path / "empty").suite.fixture_name == "fx"


def test_unknown_reference_lists_the_saved_runs(tmp_path: Path):
    save_run("saved-one", _run(), tmp_path)
    with pytest.raises(RunError, match="saved-one"):
        load_run("nope", tmp_path)
    with pytest.raises(RunError, match="Saved runs: none"):
        load_run("nope", tmp_path / "missing")


def test_unreadable_files_raise_run_errors_that_name_the_file(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("garbage", encoding="utf-8")
    with pytest.raises(RunError, match="bad.json"):
        load_run_file(bad)
    binary = tmp_path / "bin.json"
    binary.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(RunError):
        load_run_file(binary)
    with pytest.raises(RunError, match="Cannot read"):
        load_run_file(tmp_path / "absent.json")


# --- Listing -----------------------------------------------------------------------------


def test_list_runs_handles_missing_folders_and_bad_files(tmp_path: Path):
    assert list_runs(tmp_path / "nowhere") == []
    run = _run()
    save_run("good", run, tmp_path)
    (tmp_path / "bad.json").write_text("garbage", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    listings = {item.name: item for item in list_runs(tmp_path)}
    assert set(listings) == {"bad", "good"}
    assert listings["good"].selected_hits == str(run.suite.overall.selected.hits)
    assert listings["good"].fixture_name == "fx" and listings["good"].k == 5
    assert "not valid JSON" in listings["bad"].error
    assert saved_names(tmp_path) == ["bad", "good"]