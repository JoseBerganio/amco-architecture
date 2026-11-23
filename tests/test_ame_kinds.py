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
from datetime import datetime, timezone
from pathlib import Path

import pytest

import amco.ame as ame
from amco.config import context_settings
from amco.evaluation import fts5_available
from amco.ranking import RankingWeights, rank_memories
from amco.storage import add_memory, search_candidates
from amco.summaries import summary_limit
from amco.working import WorkingMemory

PERIOD = {"period_start": "2026-11-19 09:00:00", "period_end": "2026-11-19 10:00:00"}
HISTORY_QUESTION = "What did we decide last time about storage?"


@pytest.fixture(autouse=True)
def _clean_amco_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("AMCO_"):
            monkeypatch.delenv(name)


def _use_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "t.sqlite3"
    monkeypatch.setenv("AMCO_DB_PATH", str(db))
    return db


# --- format_memory ----------------------------------------------------------------


def test_a_fact_line_is_exactly_what_it_always_was():
    memory = {"id": 3, "category": "tech", "content": "Uses SQLite"}
    assert ame.format_memory(memory) == "- [Memory 3 | tech] Uses SQLite"
    assert ame.format_memory({**memory, "kind": "fact", "period_start": "2026-11-19"}) == (
        "- [Memory 3 | tech] Uses SQLite"
    )
    assert ame.format_memory({**memory, "kind": None}) == "- [Memory 3 | tech] Uses SQLite"


def test_a_summary_line_shows_its_kind_and_day():
    memory = {"id": 7, "category": "session", "content": "We chose SQLite", "kind": "summary", **PERIOD}
    assert ame.format_memory(memory) == "- [Memory 7 | summary 2026-11-19 | session] We chose SQLite"


def test_a_record_without_a_period_shows_only_its_kind():
    memory = {"id": 9, "category": "ops", "content": "Migration done", "kind": "record"}
    assert ame.format_memory(memory) == "- [Memory 9 | record | ops] Migration done"


def test_a_multi_day_summary_shows_both_days():
    memory = {
        "id": 4, "category": "session", "content": "Week recap", "kind": "summary",
        "period_start": "2026-11-16", "period_end": "2026-11-20",
    }
    assert ame.format_memory(memory) == "- [Memory 4 | summary 2026-11-16..2026-11-20 | session] Week recap"
    
    
# --- The report and /why ---------------------------------------------------------------


def test_the_report_lists_non_fact_kinds(tmp_path: Path, monkeypatch):
    db = _use_db(tmp_path, monkeypatch)
    fact = add_memory("Storage is SQLite", db_path=db)
    summary = add_memory(
        "Recap of storage work", kind="summary", category="session", db_path=db, **PERIOD
    )

    prepared = ame.prepare(HISTORY_QUESTION, WorkingMemory())

    assert dict(prepared.report.selected_kinds) == {fact: "fact", summary: "summary"}
    text = "\n".join(prepared.report.lines())
    assert f"Kinds: #{summary} summary" in text
    assert f"#{fact} fact" not in text


def test_a_fact_only_context_prints_no_kinds_line(tmp_path: Path, monkeypatch):
    db = _use_db(tmp_path, monkeypatch)
    fact = add_memory("Storage is SQLite", db_path=db)

    prepared = ame.prepare(HISTORY_QUESTION, WorkingMemory())

    assert prepared.report.selected_kinds == [(fact, "fact")]
    assert "Kinds" not in "\n".join(prepared.report.lines())


def test_the_prompt_carries_the_summary_label(tmp_path: Path, monkeypatch):
    db = _use_db(tmp_path, monkeypatch)
    add_memory("Recap of storage work", kind="summary", category="session", db_path=db, **PERIOD)

    prepared = ame.prepare(HISTORY_QUESTION, WorkingMemory())

    assert "summary 2026-11-19" in prepared.messages[0]["content"]
    
    
# --- S11-14: measure before changing ranking ------------------------------------------


@pytest.mark.parametrize("context, reserved", [(None, None), ("1024", "512")])
def test_a_summary_of_exactly_the_limit_still_fits_the_memory_budget(
    tmp_path: Path, monkeypatch, context, reserved
):
    """The label adds about 11 tokens that summary_limit() does not count. This pins that
    the margin is large enough at the default settings and at a small context."""
    db = _use_db(tmp_path, monkeypatch)
    if context:
        monkeypatch.setenv("AMCO_CONTEXT_TOKENS", context)
        monkeypatch.setenv("AMCO_RESERVED_OUTPUT_TOKENS", reserved)
    limit = summary_limit(*context_settings())
    # n words of "storage" are 8n - 1 characters, which the estimator counts as 2n tokens.
    content = " ".join(["storage"] * (limit // 2))
    memory_id = add_memory(content, kind="summary", category="session", db_path=db, **PERIOD)

    prepared = ame.prepare("What do we know about storage?", WorkingMemory())

    assert [m["id"] for m in prepared.memories] == [memory_id]
    assert prepared.report.skipped == []


def test_a_history_question_retrieves_a_summary_saved_in_an_earlier_session(
    tmp_path: Path, monkeypatch
):
    db = _use_db(tmp_path, monkeypatch)
    add_memory(
        "We settled on session cookies instead of JWT after the security review.",
        kind="summary", category="session", source="chat", source_session="aaaa1111",
        db_path=db, **PERIOD,
    )

    prepared = ame.prepare("What did we decide last time about JWT?", WorkingMemory())  # a new session

    assert prepared.report.analysis.wants_history is True
    assert [m["kind"] for m in prepared.memories] == ["summary"]
    assert "summary 2026-11-19" in prepared.messages[0]["content"]


def test_the_history_cue_moves_a_long_term_score_by_only_a_few_hundredths():
    """The long-term demotion lives in the usefulness term only, so lifting it is a small effect."""
    weights = RankingWeights()
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    memory = {
        "id": 1, "match_score": 1.0, "confidence": 1.0, "use_count": 0,
        "updated_at": "2026-11-19 00:00:00", "memory_type": "long_term",
    }
    plain = rank_memories([memory], weights=weights, now=now)[0]["score"]
    history = rank_memories([memory], weights=weights, now=now, history=True)[0]["score"]
    assert history - plain == pytest.approx(weights.usefulness * (0.5 - 0.3))
    assert history - plain < 0.05


@pytest.mark.skipif(not fts5_available(), reason="SQLite build has no FTS5")
def test_a_long_summary_scores_lower_than_a_short_fact_for_the_same_word(tmp_path: Path):
    """Finding (Sprint 11a): BM25 penalizes long documents, and relevance carries weight 0.65.
    Both memories are persistent here, so only the length differs. Not fixed in this sprint."""
    db = tmp_path / "t.sqlite3"
    add_memory("The storage engine is SQLite.", db_path=db)
    add_memory(
        "Recap of a long planning conversation where we walked through hosting costs, "
        "invoicing, onboarding, pricing, staffing and the roadmap, and also touched on "
        "storage briefly before moving on to the next agenda item and closing the meeting.",
        kind="summary", memory_type="persistent", category="session", db_path=db,
    )
    for filler in ("The garden needs watering.", "Lunch is at noon.", "The printer is broken."):
        add_memory(filler, db_path=db)  # keeps the BM25 idf of "storage" positive

    scores = {m["kind"]: m["match_score"] for m in search_candidates("storage", db_path=db)}

    assert scores["fact"] > scores["summary"]