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

import ast
import importlib
import sqlite3
from pathlib import Path

import pytest

import amco.storage as storage
from amco.storage import db as db_module

SURFACE = {
    "amco.storage.text": ["STOPWORDS", "extract_terms", "normalize_content", "term_similarity"],
    "amco.storage.db": ["connect", "session", "rebuild_index", "_has_fts"],
    "amco.storage.memories": [
        "VALID_TYPES", "DEFAULT_CONFIDENCE", "memory_status", "add_memory",
        "list_memories", "get_memory", "update_memory", "delete_memory", "record_usage",
    ],
    "amco.storage.hygiene": [
        "SIMILARITY_THRESHOLD", "supersede_memory", "restore_memory", "check_duplicates",
    ],
    "amco.storage.search": ["MAX_QUERY_TERMS", "search_candidates", "search_memories"],
}
CASES = [(module, name) for module, names in SURFACE.items() for name in names]
RE_EXPORTED = [case for case in CASES if case[1] != "_has_fts"]


def _fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


@pytest.mark.parametrize("module, name", CASES)
def test_name_lives_in_its_module(module, name):
    assert hasattr(importlib.import_module(module), name)


@pytest.mark.parametrize("module, name", RE_EXPORTED)
def test_package_re_exports_the_same_object(module, name):
    assert getattr(storage, name) is getattr(importlib.import_module(module), name)


def test_old_single_file_module_is_gone():
    assert not (Path(storage.__file__).parent.parent / "storage.py").exists()


def test_package_init_only_re_exports():
    tree = ast.parse(Path(storage.__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.ImportFrom, ast.Expr)):
            continue
        assert isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["__all__"], (
            f"unexpected code in storage/__init__.py at line {node.lineno}"
        )


@pytest.mark.skipif(not _fts5_available(), reason="SQLite build has no FTS5")
def test_patching_db_has_fts_reaches_search_and_rebuild(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "t.sqlite3"
    storage.add_memory("Users prefer a short answer", db_path=db_file)
    assert len(storage.search_candidates("answers", db_path=db_file)) == 1

    monkeypatch.setattr(db_module, "_has_fts", lambda conn: False)
    assert storage.search_candidates("answers", db_path=db_file) == []
    assert storage.rebuild_index(db_path=db_file) is False