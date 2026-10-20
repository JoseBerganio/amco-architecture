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

"""Contract: the database schema must not change during the 0.5.0 refactor.

Compares tables, columns, triggers and the FTS table (whitespace-normalized SQL)
against a snapshot taken from v0.2.0.

Regenerate the snapshot ONLY from v0.2.0 code:  python tests/test_contract_schema.py
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from amco.storage import connect, list_memories

SNAPSHOT = Path(__file__).parent / "snapshots" / "schema_fingerprint.json"


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


def _normalize(sql):
    return " ".join(sql.split()) if sql else None


def fingerprint(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        objects = [
            [kind, name, table, _normalize(sql)]
            for kind, name, table, sql in conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE 'memories_fts_%' "
                "ORDER BY type, name"
            )
        ]
        columns = {
            table: [list(row[1:]) for row in conn.execute(f"PRAGMA table_info({table})")]
            for table in ("memories", "memories_fts")
        }
    finally:
        conn.close()
    return json.loads(json.dumps({"objects": objects, "columns": columns}))


def _expected() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@needs_fts5
def test_fresh_database_matches_v020_schema(tmp_path: Path):
    db = tmp_path / "fresh.sqlite3"
    connect(db).close()
    assert fingerprint(db) == _expected()


@needs_fts5
def test_sprint1_database_migrates_to_the_v020_schema(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO memories(content) VALUES ('old memory')")
    conn.commit()
    conn.close()

    records = list_memories(db_path=db)  # opening the database migrates it
    assert [r["content"] for r in records] == ["old memory"]
    assert fingerprint(db) == _expected()


if __name__ == "__main__":
    SNAPSHOT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "snapshot.sqlite3"
        connect(db).close()
        data = fingerprint(db)
    SNAPSHOT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {SNAPSHOT}")