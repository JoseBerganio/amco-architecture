import sqlite3
from pathlib import Path

import pytest

import amco.storage as storage
from amco.storage import (
    add_memory,
    delete_memory,
    extract_terms,
    get_memory,
    rebuild_index,
    record_usage,
    search_memories,
    update_memory,
)


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


def test_extract_terms_drops_stopwords_punctuation_and_duplicates():
    assert extract_terms("What is the SQLite database? SQLite!") == ["sqlite", "database"]


def test_extract_terms_splits_on_underscores_and_respects_limit():
    assert extract_terms("memory_type") == ["memory", "type"]
    assert extract_terms("alpha beta gamma delta", limit=2) == ["alpha", "beta"]


@needs_fts5
def test_stemming_matches_word_forms(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("Users prefer short answers", db_path=db)
    assert len(search_memories("short answer", db_path=db)) == 1


def test_query_with_only_stopwords_returns_nothing(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("The garden needs watering", db_path=db)
    assert search_memories("What is the?", db_path=db) == []


def test_fts_syntax_in_queries_does_not_crash(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("AMCO uses sqlite", db_path=db)
    results = search_memories('sqlite" OR (* NEAR', db_path=db)
    assert [m["content"] for m in results] == ["AMCO uses sqlite"]


@needs_fts5
def test_index_follows_update_and_delete(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    memory_id = add_memory("alpha topic", db_path=db)
    assert len(search_memories("alpha", db_path=db)) == 1

    update_memory(memory_id, content="beta topic", db_path=db)
    assert search_memories("alpha", db_path=db) == []
    assert len(search_memories("beta", db_path=db)) == 1

    delete_memory(memory_id, db_path=db)
    assert search_memories("beta", db_path=db) == []


@needs_fts5
def test_legacy_rows_are_indexed_by_migration(tmp_path: Path):
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
    conn.execute("INSERT INTO memories(content) VALUES ('old memory about zebras')")
    conn.commit()
    conn.close()

    results = search_memories("zebras", db_path=db)
    assert len(results) == 1
    assert results[0]["confidence"] == 1.0
    assert results[0]["use_count"] == 0


@needs_fts5
def test_rebuild_index_recovers_a_wiped_index(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("zebras live here", db_path=db)
    raw = sqlite3.connect(db)
    raw.execute("INSERT INTO memories_fts(memories_fts) VALUES ('delete-all')")
    raw.commit()
    raw.close()
    assert search_memories("zebras", db_path=db) == []

    assert rebuild_index(db_path=db) is True
    assert len(search_memories("zebras", db_path=db)) == 1


def test_keyword_fallback_when_fts_is_unavailable(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite3"
    add_memory("Project uses Python and SQLite", db_path=db)
    add_memory("The garden needs watering", db_path=db)
    monkeypatch.setattr(storage, "_has_fts", lambda conn: False)
    results = search_memories("SQLite", db_path=db)
    assert [m["content"] for m in results] == ["Project uses Python and SQLite"]
    assert rebuild_index(db_path=db) is False


def test_confidence_breaks_ties_and_results_carry_score_parts(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    add_memory("project uses sqlite", db_path=db, confidence=0.2)
    add_memory("project uses sqlite", db_path=db, confidence=1.0)
    results = search_memories("sqlite", db_path=db)
    assert [m["confidence"] for m in results] == [1.0, 0.2]
    assert "score" in results[0] and "score_parts" in results[0]


def test_limit_is_respected(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    for i in range(6):
        add_memory(f"sqlite note {i}", db_path=db)
    assert len(search_memories("sqlite", limit=3, db_path=db)) == 3


def test_confidence_is_validated_stored_and_updatable(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    with pytest.raises(ValueError):
        add_memory("x", confidence=1.5, db_path=db)
    memory_id = add_memory("guess", confidence=0.4, db_path=db)
    assert get_memory(memory_id, db_path=db)["confidence"] == 0.4
    assert update_memory(memory_id, confidence=0.9, db_path=db) is True
    assert get_memory(memory_id, db_path=db)["confidence"] == 0.9
    with pytest.raises(ValueError):
        update_memory(memory_id, confidence=-0.1, db_path=db)


def test_record_usage_increments_counts(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    first = add_memory("one", db_path=db)
    second = add_memory("two", db_path=db)
    record_usage([first, first, 999], db_path=db)  # duplicates count once; unknown ids are ignored
    record_usage([], db_path=db)
    assert get_memory(first, db_path=db)["use_count"] == 1
    assert get_memory(second, db_path=db)["use_count"] == 0