# AMCO — Development Progress

Running log of what has been built, changed, and verified in each sprint.
Project: **AMCO (Adaptive Memory Controller)** — a local-first memory orchestration layer for local LLMs.
Last updated: 2026-10-15

## Status at a glance

| Sprint | Objective | Status |
|--------|-----------|--------|
| 1 | Python project foundation and CLI | Done |
| 2 | SQLite storage and basic memory commands | Done |
| 3 | Working Memory, context budgeting, and local model setup | Done |
| 4 | Full-text search and ranking | Done |

Current release: `0.1.0` (published). The 0.2 series is in development; the version string stays at `0.1.0` until the 0.2.0 release.
Default model: `qwen2.5:3b` (4-bit quantized) via Ollama

---

## Sprint 1 — Foundation and CLI

**Goal:** an installable `amco` command that runs, shows help, and has automated tests.

**What was delivered**

The starter went slightly beyond the original "foundation only" scope and produced a small working vertical slice:

- Installable Python package (`pyproject.toml`, `src/` layout, `amco` console script).
- CLI built with Typer and Rich.
- SQLite storage with a single `memories` table (`id`, `content`, `category`, `source`, `created_at`).
- Keyword retrieval: case-insensitive term counting, top results returned.
- Ollama adapter using HTTPX, with clear errors when Ollama is unreachable or returns a bad response.
- Chat engine that retrieves memories and sends them to the model inside a system prompt that treats memories as untrusted reference data, not instructions.
- Tests for storage and for the engine (mocked model, so Ollama is not required).

**Commands available after Sprint 1**

`amco version`, `amco init`, `amco chat`, `amco memory add | list | search | delete`

**Acceptance checks (all met)**

1. `amco --help` shows the CLI commands.
2. `amco init` creates the local SQLite database.
3. A memory can be added, listed, searched, and deleted.
4. `amco chat` retrieves relevant memories and passes them to Ollama.
5. A clear error is shown when Ollama is unavailable.
6. Automated tests pass without Ollama.

**Issues found in review (fixed in Sprint 2)**

- `console.print(..., err=True)` in `memory_delete` is not a valid Rich argument and would raise `TypeError` when deleting a nonexistent ID.
- SQLite connections were committed but never closed.
- `__import__('os')` was used inside `chat` instead of a normal import.
- No `.gitignore` for `__pycache__` and `*.egg-info`.

---

## Sprint 2 — Storage and memory management

**Goal:** memories can be saved, listed, inspected, updated, and deleted through tested operations.

### Added

- `amco memory inspect <id>` — shows a memory's full content and metadata.
- `amco memory update <id>` — changes `--content`, `--category`, or `--type`, and refreshes `updated_at`.
- `memory_type` field on every memory: `persistent` or `long_term` (a first step toward the PM and LTM split in the brief).
- `updated_at` timestamp on every memory.
- `--type` option on `memory add`, and `--type` filter on `memory list`.
- Storage functions `get_memory()` and `update_memory()`.
- `session()` context manager in `storage.py`: commits on success, rolls back on error, always closes the connection.
- Automatic schema migration, so databases created in Sprint 1 are upgraded in place without losing data. Old rows receive `memory_type = 'persistent'` and `updated_at = created_at`.
- Input validation: empty content is rejected, unknown memory types are rejected, and `update` requires at least one field.
- `.gitignore` for `__pycache__/`, `*.pyc`, `*.egg-info/`, `.venv/`, `.pytest_cache/`.

### Changed

- `memory list` now shows ID, Type, Category, Updated, and Content.
- `memory search` output now includes the memory type and category.
- `memory inspect`, `memory update`, and `memory delete` report a missing ID on stderr and exit with code 1.
- `init` uses the new `session()` helper.
- `add_memory()` accepts an optional `memory_type`; existing callers keep working.

### Fixed

- Deleting a nonexistent memory no longer crashes (the invalid `err=True` argument was replaced with a separate `Console(stderr=True)`).
- Database connections are now closed after every operation.
- Rich markup no longer swallows the `[type/category]` label in search output.
- Removed the `__import__('os')` workaround in `chat`.

### Tests

- Sprint 1 baseline: 5 tests (4 storage, 1 engine).
- Added 8 storage tests and 4 CLI tests (new `tests/test_cli.py`).
- Total after Sprint 2: 17 tests, all passing without Ollama.

### Acceptance criteria (all met)

1. `amco memory inspect <id>` shows all fields.
2. `amco memory update <id>` changes content, category, or type and refreshes `updated_at`.
3. Memories carry `updated_at` and `memory_type`.
4. `amco memory list --type ...` filters by type.
5. Existing databases migrate automatically.
6. Deleting a nonexistent ID prints a clean error and exits with code 1.
7. Connections are closed properly.
8. Tests pass without Ollama.

**Verification:** `pytest` passed in full, and the CLI commands were run manually and behaved as expected.

---

## Sprint 3 — Working Memory, context budgeting, and local model

**Goal:** `amco chat` keeps conversation state, assembles its prompt within a token budget, and runs against a real local model.

### Added

- **Working Memory** (`src/amco/working.py`): a `WorkingMemory` object holding the current session's turns, a pinned task, a count of dropped turns, and the size of the last prompt.
- **Token estimation** via `estimate_tokens()` (roughly 4 characters per token). All counting goes through this one function so a real tokenizer can replace it later.
- **History trimming**: when the context fills up, the oldest whole turns are dropped first, and the remaining history always starts on a user turn.
- **Context budgeting** in the engine: usable space is the context limit minus reserved output tokens. Retrieved memories get at most half of the space left after the fixed parts, and conversation history gets the rest.
- **Memory selection** (`select_memories()`): candidates are kept in ranked order while they fit the budget. A memory that does not fit is skipped, never truncated, so its meaning is not changed.
- **Chat commands**: `/task`, `/remember`, `/status`, `/clear`, `/help`, plus `/exit` and `/quit`.
  - `/task <text>` pins the current objective in the system prompt; `/task` shows it; `/task clear` removes it.
  - `/remember <text>` saves text to Persistent Memory (category `chat`) by explicit user approval.
  - `/status` shows turns, estimated tokens, dropped turns, last prompt size, and the task.
  - `/clear` resets Working Memory.
- **Central configuration** (`src/amco/config.py`) for model name, Ollama URL, context settings, and timeout.
- **Local model**: default model is now `qwen2.5:3b` (4-bit quantized) through Ollama.
- **Context window sent to Ollama**: AMCO passes its context limit as `num_ctx`, so the model's real window matches the budget AMCO plans for.
- **Missing-model error**: a 404 from Ollama now says `Model '<name>' was not found. Run: ollama pull <name>`.

### Changed

- `answer(query, working=None)` accepts an optional `WorkingMemory`. Without one, it behaves statelessly as before.
- The chat loop keeps one `WorkingMemory` per session and records a turn only after the model call succeeds, so a failed call leaves no trace.
- The model's reply is printed with Rich markup disabled, so replies containing text like `[/code]` can no longer crash the chat loop.
- Request timeout raised from 120 s to 300 s by default (`AMCO_TIMEOUT_SECONDS`), since a 3B model on CPU can be slow.
- `engine.py` and `cli.py` read settings from `config.py` instead of reading environment variables directly.

### Tests

- Added `tests/test_working.py` (8 tests): token estimate, message format, role validation, trimming (oldest-first, user-first, no-op, zero budget), task and clear.
- Added `tests/test_engine_context.py` (5 tests): history sent and recorded, failed call records nothing, task in the system prompt, history trimmed to the context budget, oversize memory skipped without truncation.
- Added `tests/test_model.py` (3 tests): default model is Qwen, `num_ctx` is sent, missing model gives a pull hint.
- Added 2 CLI tests: chat commands (`/task`, `/remember`, `/status`) and a single shared Working Memory across turns.
- Total after Sprint 3: 35 tests, none of which need Ollama.

### Acceptance criteria

1. Chat remembers earlier turns within a session.
2. History is trimmed oldest-first, in whole turns, with output space reserved.
3. Retrieved memories fit a token budget and are never truncated.
4. `/task`, `/remember`, `/clear`, `/status`, and `/help` work.
5. A failed model call does not alter Working Memory.
6. Tests pass without Ollama.

**Verification to complete:** run `pytest`, then a live `amco chat` against `qwen2.5:3b` and exercise the commands.

### Notes from this sprint

- Retrieval still matches only the current message, so vague follow-ups rely on conversation history rather than pulling new memories.
- Dropped turns are discarded, not summarized.
- A 3B model follows memory instructions less reliably than larger models. When testing, check the `Retrieved memories: #...` line to separate retrieval quality from model quality.

---

## Sprint 4 — Full-text search, ranking, and follow-up retrieval (0.2 series)

**Goal:** retrieval finds relevant memories more reliably, ranks them with an explainable formula, and no longer fails on short follow-up questions.

### Added

- **SQLite FTS5 index** (`memories_fts`): external-content table over `memories`, indexing content and category with Porter stemming. Triggers keep it in sync on insert, update, and delete. Existing databases are indexed automatically on first connect.
- **Keyword fallback:** if the SQLite build has no FTS5, search falls back to the Sprint 1–3 keyword counter instead of failing.
- **Safe query building** (`extract_terms()`): queries are reduced to meaningful terms (no punctuation, stopwords, one-letter tokens, or duplicates, at most 12 terms) and each term is quoted, so user input can never break FTS syntax.
- **Ranking module** (`src/amco/ranking.py`): `Score = wR·R + wC·C + wF·F + wU·U`.
  - **R (relevance):** BM25 score, normalized against the best candidate in the pool.
  - **C (confidence):** new `confidence` column, 0 to 1, default 1.0 (memories added by the user are treated as confirmed).
  - **F (freshness):** exponential decay on `updated_at`, 180-day half-life by default.
  - **U (usefulness):** half a type prior (persistent 1.0, long_term 0.6) and half a log-scaled usage count.
  - Default weights: 0.65 / 0.15 / 0.05 / 0.15. Freshness is deliberately low because recency is not universal importance.
- **Usage tracking:** `use_count` column, incremented only when a memory was sent to the model in a successful call. A failed model call or a failed usage write never costs the user a reply.
- **Follow-up retrieval** (`retrieval_query()`): when the current message has fewer than 3 meaningful terms (for example "Is it fast?"), terms from the last 2 user turns are added to the search. Detailed questions are searched as written, and the current message's terms always come first.
- **Diagnostics:** `amco memory search ... --explain` prints the score and its R/C/F/U parts for each result, and chat shows each retrieved memory's score.
- **Commands and options:** `--confidence` on `memory add` and `memory update`, `amco memory reindex` to rebuild the index from the stored memories, a `Conf` column in `memory list`, and confidence and usage count in `memory inspect`.
- **Configuration:** `AMCO_WEIGHT_RELEVANCE`, `AMCO_WEIGHT_CONFIDENCE`, `AMCO_WEIGHT_FRESHNESS`, `AMCO_WEIGHT_USEFULNESS`, `AMCO_FRESHNESS_HALF_LIFE_DAYS`, `AMCO_FOLLOWUP_MIN_TERMS`, `AMCO_FOLLOWUP_TURNS`.

### Changed

- `search_memories()` now retrieves a candidate pool (at least 20) with FTS5, re-ranks it, and returns the top results. Each result carries `score` and `score_parts`.
- Matching is now by stemmed word instead of substring (for example "answers" matches "answer", but "sql" no longer matches "sqlite").
- `answer()` searches with `retrieval_query()` and records usage after a successful model call.
- `add_memory()` and `update_memory()` accept `confidence` (added as the last parameter, so existing callers keep working).
- Database migration now also adds `confidence` and `use_count` to databases from earlier sprints.

### Fixed

- Memory content containing square brackets (such as `[/x]`) could break Rich markup in `memory search` output. Content is now escaped.

### Tests

- Added `tests/test_ranking.py` (10 tests): freshness decay, usefulness, relevance and confidence ordering, old-but-relevant beats recent-but-unrelated, score parts, custom and environment weights.
- Added `tests/test_search.py` (13 tests): term extraction, stemming, stopword-only and FTS-syntax queries, index sync on update and delete, legacy-database migration, index rebuild, keyword fallback, confidence tie-breaking, limits, confidence validation, usage counting.
- Added `tests/test_engine_retrieval.py` (6 tests): follow-up query building, end-to-end follow-up retrieval, usage counted only after a successful call.
- Added 3 CLI tests: `--explain`, `--confidence`, `reindex`.
- Total after Sprint 4: 67 tests, none of which need Ollama. FTS5-specific tests are skipped automatically on SQLite builds without FTS5.

### Acceptance criteria

1. Search uses FTS5 and handles word forms (stemming).
2. Results are ranked by relevance, confidence, freshness, and usefulness, with weights configurable.
3. `amco memory search --explain` shows how each result was scored.
4. Short follow-up questions retrieve memories from the previous topic.
5. Sprint 1–3 databases migrate automatically and their memories are searchable.
6. Search still works, with the keyword fallback, if FTS5 is unavailable.
7. The index can be rebuilt with `amco memory reindex`.
8. Tests pass without Ollama.

**Verification:** `pytest` passed in full.

### Notes from this sprint

- Relevance is normalized within the candidate pool, so a score of 1.0 means "best match among these candidates", not an absolute measure.
- Follow-up retrieval borrows from user turns only. A pronoun whose topic appeared only in the assistant's reply will not resolve.
- The ranking weights are a starting heuristic, as the brief says, and still need tuning against real tasks.

____

## Current command reference

| Command | Purpose |
|---------|---------|
| `amco version` | Show the version |
| `amco init` | Create the workspace and database |
| `amco chat` | Interactive chat with Working Memory and memory retrieval |
| `amco memory add "text" [-c category] [-t type] [--confidence 0-1]` | Save a memory |
| `amco memory update <id> [--content ...] [-c ...] [-t ...] [--confidence ...]` | Edit a memory |
| `amco memory search "words" [--limit N] [--explain]` | Ranked full-text search |
| `amco memory reindex` | Rebuild the search index |
| `amco memory list [-t type]` | List memories |
| `amco memory inspect <id>` | Show one memory in full |
| `amco memory update <id> [--content ...] [-c ...] [-t ...]` | Edit a memory |
| `amco memory search "words" [--limit N]` | Keyword search |
| `amco memory delete <id> [--yes]` | Delete a memory |

**Chat commands:** `/task`, `/remember`, `/status`, `/clear`, `/help`, `/exit`

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `AMCO_DB_PATH` | `~/.amco/amco.sqlite3` | Database location |
| `AMCO_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `AMCO_MODEL` | `qwen2.5:3b` | Model name |
| `AMCO_CONTEXT_TOKENS` | `4096` | Context window (also sent to Ollama as `num_ctx`) |
| `AMCO_RESERVED_OUTPUT_TOKENS` | `512` | Space kept free for the reply |
| `AMCO_MEMORY_TOKENS` | `1024` | Cap on tokens spent on retrieved memories |
| `AMCO_TIMEOUT_SECONDS` | `300` | Model request timeout |
| `AMCO_WEIGHT_RELEVANCE` | `0.65` | Ranking weight for relevance |
| `AMCO_WEIGHT_CONFIDENCE` | `0.15` | Ranking weight for confidence |
| `AMCO_WEIGHT_FRESHNESS` | `0.05` | Ranking weight for freshness |
| `AMCO_WEIGHT_USEFULNESS` | `0.15` | Ranking weight for usefulness |
| `AMCO_FRESHNESS_HALF_LIFE_DAYS` | `180` | Days for the freshness score to halve |
| `AMCO_FOLLOWUP_MIN_TERMS` | `3` | Fewer meaningful terms than this triggers history-aware retrieval |
| `AMCO_FOLLOWUP_TURNS` | `2` | User turns borrowed for follow-up retrieval |

## Project structure

```
src/amco/
├── __init__.py
├── cli.py        # Typer commands and chat loop
├── config.py     # Environment-based settings
├── engine.py     # Retrieval query, memory selection, prompt assembly
├── model.py      # Ollama adapter
├── ranking.py    # Scoring formula (relevance, confidence, freshness, usefulness)
├── storage.py    # SQLite storage, FTS5 index, migration, search
└── working.py    # Working Memory and token estimation
tests/
├── test_cli.py
├── test_engine.py
├── test_engine_context.py
├── test_engine_retrieval.py
├── test_model.py
├── test_ranking.py
├── test_search.py
├── test_storage.py
└── test_working.py
```

## Known gaps (deferred to later sprints)

- No semantic (embedding) search; FTS5 matches words and their stems, not meaning.
- Follow-up retrieval uses only recent user turns, not assistant replies.
- Ranking weights are untuned defaults; there is no evaluation set yet.
- Persistent vs. long-term is a label plus a small usefulness prior; no lifecycle rules or automatic promotion.
- No supersession, expiry, or provenance beyond `source`; confidence is set manually.
- No conflict detection or deduplication.
- No summarization of dropped turns.
- No automatic memory evaluation; memories are saved only by explicit command.
- Token counts are an estimate, not a real tokenizer.
- No `models`, `stats`, or `config` commands, and no TOML configuration.
- Model adapter is a single function, not yet a base interface.

---

## Up next

Sprint 5 is not yet planned. Candidates from the roadmap: memory lifecycle rules (promotion, supersession, expiry), conflict detection and deduplication, and a model adapter interface. Semantic retrieval should wait until there is a baseline to measure it against.

## Release 0.1.0

Sprints 1 to 3 conclude the 0.1.0 release. Sprint 4 onward belongs to the 0.2 series.

- Licensed under GPL-2.0-or-later (`LICENSE` file, SPDX and GPL notice header in every source file, license declared in `pyproject.toml`).
- Repository published on GitHub and tagged `v0.1.0`.
- Default model: `qwen2.5:3b` (4-bit quantized) via Ollama. The model has its own license, separate from AMCO's.

---

