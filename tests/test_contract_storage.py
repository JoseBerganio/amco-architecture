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

"""Contract: storage operations must open the same connections and run the same SQL.

For each operation, the snapshot holds the number of sqlite3.connect() calls and
the whitespace-normalized SQL text passed to the connection. Parameters are not
recorded.

Regenerate the snapshot only inside the sprint that deliberately changes storage SQL,
and read the diff first:  python tests/test_contract_storage.py
Last regenerated in Sprint 10a (schema versioning: connect() reads user_version
instead of running PRAGMA table_info and an UPDATE on every call).
"""

import json
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

import amco.storage as storage
from amco.storage import (
    add_memory,
    check_duplicates,
    connect,
    delete_memory,
    get_memory,
    list_memories,
    rebuild_index,
    record_usage,
    restore_memory,
    search_candidates,
    search_memories,
    supersede_memory,
    update_memory,
)

SNAPSHOT = Path(__file__).parent / "snapshots" / "storage_operations.json"


def _fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


needs_fts5 = pytest.mark.skipif(not _fts5_available(), reason="SQLite build has no FTS5")


def _normalize(sql: str) -> str:
    return " ".join(sql.split())


@contextmanager
def _recording():
    log: list[str] = []
    counter = {"connects": 0}

    class Recording(sqlite3.Connection):
        def execute(self, sql, *args):
            log.append(_normalize(sql))
            return super().execute(sql, *args)

        def executemany(self, sql, *args):
            log.append(_normalize(sql))
            return super().executemany(sql, *args)

        def executescript(self, script):
            log.append(_normalize(script))
            return super().executescript(script)

    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counter["connects"] += 1
        kwargs["factory"] = Recording
        return real_connect(*args, **kwargs)

    sqlite3.connect = counting_connect
    try:
        yield counter, log
    finally:
        sqlite3.connect = real_connect


def _seed(db: Path) -> None:
    """Memories 1 and 2 are active; memory 3 is superseded by memory 1."""
    connect(db).close()
    add_memory("The project uses SQLite for storage", category="notes", db_path=db)
    add_memory("The garden needs watering on Sundays", memory_type="long_term", db_path=db)
    add_memory("Old storage used JSON files", db_path=db)
    supersede_memory(3, 1, db_path=db)


CASES = {
    "connect_fresh": (lambda db: None, lambda db: connect(db).close()),
    "add_memory": (_seed, lambda db: add_memory("A new note", db_path=db)),
    "add_memory_supersedes": (
        _seed, lambda db: add_memory("Replacement", supersedes=2, db_path=db)
    ),
    "list_memories": (_seed, lambda db: list_memories(db_path=db)),
    "list_memories_filtered": (
        _seed,
        lambda db: list_memories(db_path=db, memory_type="long_term", include_inactive=True),
    ),
    "get_memory": (_seed, lambda db: get_memory(1, db_path=db)),
    "update_memory": (
        _seed,
        lambda db: update_memory(
            1, content="changed", confidence=0.5, expires_at="2999-12-31", db_path=db
        ),
    ),
    "delete_memory": (_seed, lambda db: delete_memory(1, db_path=db)),
    "delete_missing_memory": (_seed, lambda db: delete_memory(999, db_path=db)),
    "supersede_memory": (_seed, lambda db: supersede_memory(2, 1, db_path=db)),
    "restore_memory": (_seed, lambda db: restore_memory(3, db_path=db)),
    "check_duplicates": (
        _seed, lambda db: check_duplicates("The project uses SQLite for storage", db_path=db)
    ),
    "search_candidates": (_seed, lambda db: search_candidates("storage", db_path=db)),
    "search_memories": (_seed, lambda db: search_memories("storage", db_path=db)),
    "record_usage": (_seed, lambda db: record_usage([1, 2], db_path=db)),
    "rebuild_index": (_seed, lambda db: rebuild_index(db_path=db)),
}


def run_case(name: str, folder: Path) -> dict:
    setup, operation = CASES[name]
    db = folder / f"{name}.sqlite3"
    setup(db)
    with _recording() as (counter, log):
        operation(db)
    return {"connects": counter["connects"], "statements": list(log)}


def _expected() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_snapshot_covers_every_case():
    assert set(_expected()) == set(CASES)


@needs_fts5
@pytest.mark.parametrize("name", list(CASES))
def test_operation_matches_the_pre_split_snapshot(name: str, tmp_path: Path):
    assert run_case(name, tmp_path) == _expected()[name]


# --- The _has_fts seam ------------------------------------------------------


@needs_fts5
def test_patching_has_fts_forces_the_keyword_fallback_and_blocks_rebuild(
    tmp_path: Path, monkeypatch
):
    db = tmp_path / "t.sqlite3"
    add_memory("Users prefer a short answer", db_path=db)

    # With FTS5, stemming makes "answers" match "answer".
    assert len(search_candidates("answers", db_path=db)) == 1

    monkeypatch.setattr(storage.db, "_has_fts", lambda conn: False)

    # The keyword fallback counts substrings, so "answers" no longer matches.
    assert search_candidates("answers", db_path=db) == []
    assert rebuild_index(db_path=db) is False


if __name__ == "__main__":
    SNAPSHOT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        data = {name: run_case(name, Path(folder)) for name in CASES}
    SNAPSHOT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {SNAPSHOT}")