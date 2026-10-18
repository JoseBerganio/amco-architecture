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

import sqlite3
from pathlib import Path

from amco.lifecycle import Finding, apply_finding, review
from amco.storage import add_memory, get_memory, supersede_memory


def _set(db: Path, memory_id: int, **columns) -> None:
    conn = sqlite3.connect(db)
    assignments = ", ".join(f"{name} = ?" for name in columns)
    conn.execute(f"UPDATE memories SET {assignments} WHERE id = ?", (*columns.values(), memory_id))
    conn.commit()
    conn.close()


def _summary(findings):
    return [(f.memory_id, f.action) for f in findings]


def test_fresh_memories_need_no_review(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("a fresh note", db_path=db)
    assert review(db_path=db) == []


def test_expired_memory_is_flagged_for_deletion(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("temporary", db_path=db, expires_at="2000-01-01")
    assert _summary(review(db_path=db)) == [(memory_id, "delete")]


def test_superseded_memory_is_flagged_only_after_the_retention_period(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    old = add_memory("old fact", db_path=db)
    new = add_memory("new fact", db_path=db)
    supersede_memory(old, new, db_path=db)
    assert review(db_path=db) == []
    _set(db, old, superseded_at="2020-01-01 00:00:00")
    assert _summary(review(db_path=db)) == [(old, "delete")]


def test_idle_persistent_memory_is_suggested_for_archiving(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("old habit", db_path=db)
    _set(db, memory_id, created_at="2020-01-01 00:00:00", updated_at="2020-01-01 00:00:00")
    assert _summary(review(db_path=db)) == [(memory_id, "archive")]


def test_well_used_long_term_memory_is_suggested_for_promotion(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("often used note", memory_type="long_term", db_path=db)
    _set(db, memory_id, use_count=6)
    assert _summary(review(db_path=db)) == [(memory_id, "promote")]


def test_duplicates_are_resolved_in_favor_of_the_more_trusted_memory(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    weak = add_memory("same note", db_path=db, confidence=0.5)
    strong = add_memory("same note", db_path=db, confidence=1.0)
    findings = review(db_path=db)
    assert _summary(findings) == [(weak, "supersede")]
    assert findings[0].target_id == strong


def test_apply_finding_changes_memories(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("a note", db_path=db)
    assert apply_finding(Finding(memory_id, "archive", "idle"), db_path=db) is True
    assert get_memory(memory_id, db_path=db)["memory_type"] == "long_term"
    assert apply_finding(Finding(memory_id, "promote", "used"), db_path=db) is True
    assert get_memory(memory_id, db_path=db)["memory_type"] == "persistent"
    assert apply_finding(Finding(memory_id, "delete", "expired"), db_path=db) is True
    assert get_memory(memory_id, db_path=db) is None