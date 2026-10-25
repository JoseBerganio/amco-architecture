# AMCO — Development Progress

Running log of what has been built, changed, and verified in each sprint.
Project: **AMCO (Adaptive Memory Controller)** — a local-first memory orchestration layer for local LLMs.
Last updated: 2026-10-24

## Status at a glance

| Sprint | Objective | Status |
|--------|-----------|--------|
| 1 | Python project foundation and CLI | Done |
| 2 | SQLite storage and basic memory commands | Done |
| 3 | Working Memory, context budgeting, and local model setup | Done |
| 4 | Full-text search and ranking | Done |
| 5 | Adaptive Memory Engine (AME), memory hygiene, and lifecycle review | Done |
| 6 | Safety net, CI, and CLI split | Done |
| 7 | Model adapter contract and configuration centralization | Done |
| 8 | Storage package split | Done |
| 9 | Shim removal, test path migration, and release | Done |

Current release: `0.5.0`.
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

## Sprint 5 — Adaptive Memory Engine, memory hygiene, and lifecycle review (0.2 series)

**Goal:** connect task analysis, retrieval, ranking, conflict handling, context budgeting, and memory lifecycle management into one orchestration pipeline (Phase 5), with duplicate handling, supersession, and expiry as its conflict-handling and lifecycle stages.

### Added

- **AME module** (`src/amco/ame.py`): the pipeline `analyze → retrieve → resolve → budget → assemble → model call → finish`. The AME is plain software, not a language model. The model call itself stays in `engine.py` so the adapter can be swapped later.
- **Task analysis** (`analyze_task()`): rule-based classification into `chitchat`, `followup`, `instruction`, `question`, or `statement`, plus detection of history cues ("last time", "we decided", "earlier").
  - Greetings and thanks skip retrieval entirely.
  - Retrieval depth is 5 by default and 8 when the message has history cues or a task is pinned with `/task`.
  - Thin messages borrow the pinned task first, then recent user turns (extends the Sprint 4 follow-up rule).
- **History-aware ranking:** with history cues, long-term memories are no longer demoted by the usefulness prior. Nothing is filtered out; only the ranking changes.
- **Retrieval-time conflict handling:**
  - Candidates whose content is identical to a higher-ranked one are dropped before budgeting.
  - Selected memories that overlap (term similarity of at least 0.6) get a conflict note in the prompt naming the preferred memory (higher confidence, then more recently updated, then newer ID). At most 2 notes. The note is worded as "may disagree", because overlap cannot prove a contradiction.
- **Diagnostics:** every call stores a `ContextReport` on Working Memory, and `/why` in chat shows the task kind, search text, candidates with scores, selected and skipped memories (with reasons), conflicts, memory and prompt token use, turns dropped, and timings.
- **Write-time duplicate checks** (at the user-facing boundary, in `memory add` and `/remember`): exact duplicates (ignoring case, whitespace, and trailing punctuation) are blocked unless `--force`; near-duplicates only produce a warning with a hint to run `amco memory supersede`.
- **Supersession:** `superseded_by` and `superseded_at` columns. `amco memory supersede <old> <new>`, `amco memory restore <id>`, and `amco memory add --supersedes <id>` (atomic). Superseded memories are kept and inspectable but hidden from search, chat, and the default list. `amco memory list --all` shows everything with a status column.
- **Expiry:** `--expires YYYY-MM-DD` on `memory add` and `memory update` (`none` clears it). The date is the last valid day. Expired memories are hidden from retrieval but never deleted automatically.
- **Usage timestamp:** new `last_used_at` column, set whenever a memory is sent to the model.
- **Lifecycle review** (`src/amco/lifecycle.py`, `amco memory review [--apply] [--yes]`): suggests changes and applies them only with `--apply`.
  - Delete expired memories.
  - Delete superseded memories after the retention period (30 days).
  - Supersede exact duplicates in favor of the most trusted copy.
  - Archive persistent memories idle for 90 days to long-term.
  - Promote long-term memories used at least 5 times and still active to persistent.
- **Configuration:** `AMCO_STALE_DAYS`, `AMCO_PROMOTE_USES`, `AMCO_SUPERSEDED_RETENTION_DAYS`.
- **Schema migration:** databases from earlier versions gain `superseded_by`, `superseded_at`, `expires_at`, and `last_used_at` automatically.

### Changed

- `engine.py` is now a thin wrapper over the AME. `answer()`, `select_memories()`, and `retrieval_query()` keep their names and behavior.
- `search_memories()` and `list_memories()` hide superseded and expired memories by default (`include_inactive=True` shows them). `search_memories()` accepts `history=`.
- `ranking.parse_timestamp()` is now public; `usefulness()` and `rank_memories()` accept `history`.
- `WorkingMemory` gains `last_report`, which `clear()` resets.
- `delete_memory()` repairs supersession links: memories the deleted one had replaced are re-pointed to its own replacement, or revived if it had none.
- `add_memory()` stays permissive (no duplicate blocking), so the low-level storage API is unchanged for callers and tests. `add_memory()` and `update_memory()` accept `expires_at`; `add_memory()` accepts `supersedes`.
- Stopwords now include common greetings (hi, hello, hey, thanks, ok).
- `memory inspect` shows status, last-used time, and expiry.

### Tests

- Added `tests/test_hygiene.py` (12 tests), `tests/test_ame.py` (12 tests), and `tests/test_lifecycle.py` (7 tests).
- Added 2 ranking tests (history flag) and 5 CLI tests (duplicate blocking, supersede/restore/`--all`, review, bad expiry, `/why`).
- Total after Sprint 5: 105 tests, none of which need Ollama.

### Acceptance criteria

1. Every chat message goes through the AME pipeline, and `/why` explains the result.
2. Greetings skip retrieval; short follow-ups and pinned tasks improve retrieval.
3. Identical memories are blocked on add (unless `--force`) and dropped at retrieval time.
4. Overlapping memories are surfaced to the model with a precedence note.
5. A superseded memory is hidden from retrieval but kept, inspectable, and restorable.
6. An expired memory is hidden from retrieval but not deleted.
7. `amco memory review` reports lifecycle suggestions and changes nothing without `--apply`.
8. Older databases migrate automatically.
9. Tests pass without Ollama.

**Verification:** `pytest` passed in full, and the hygiene, `/why`, and review flows were run manually.

### Notes from this sprint

- Conflict detection is a term-overlap heuristic; it cannot tell a contradiction from a complementary fact.
- The task classifier is rule-based and English-only. Its effects are limited to retrieval depth and whether to skip retrieval.
- Duplicate checks scan all active memories, which is fine at prototype scale.
- `review` does not flag near-duplicates; those are only warned about at write time.

---

## Sprints 6 to 9 — Modularization update (0.5 series)

**Goal:** restructure the internals so the code is easier to maintain, test and extend, with no change to what users see or what the database contains. Detailed per-sprint records are kept in the local SPRINT.md.

**Approach:** code was moved verbatim first and tidied in separate commits, one module per commit with `pytest` after each. Existing tests stayed untouched until Sprint 9, settings are read at call time, and temporary shims kept old import paths working until the cleanup sprint.

### Sprint 6 — Safety net, CI, and CLI split

- Contract tests written against v0.2.0 before anything moved: a CLI command-tree snapshot, an import-surface test, and a database schema fingerprint.
- GitHub Actions CI on Ubuntu and Windows with Python 3.11 and 3.13, including a non-editable install check.
- `cli.py` became the `cli/` package (`common`, `system`, `memory`, `chat`). The chat loop receives the answer function, which keeps the `amco.cli.answer` test seam working.
- Fixed in review: the CLI snapshot test imported `click`, which newer Typer versions no longer install. It now reads the command objects by attribute.

### Sprint 7 — Model adapter and configuration

- New `models/` package: a `ChatModel` interface, `ModelError` (a `RuntimeError`, so existing handlers keep working), and the `OllamaChat` adapter, with its logic and error messages moved unchanged.
- `get_model()` factory and the `AMCO_PROVIDER` setting (default `ollama`; an unknown value gives a clear error). `answer()` accepts an optional `model`, so tests can inject a fake.
- All environment reads moved into `config.py` (database path, timeout, provider, ranking weights), still read at call time.
- Characterization tests pin the exact Ollama request payload and error messages.

### Sprint 8 — Storage package split

- `storage.py` became the `storage/` package: `text`, `db`, `memories`, `hygiene` and `search`, with `__init__` re-exporting the public API.
- A snapshot of every storage operation (connections opened and SQL executed) showed the split added no queries.
- An architecture test enforces the import direction `text → db → memories → hygiene → search`.
- A small temporary seam kept the existing `_has_fts` test patch working across modules.

### Sprint 9 — Cleanup and release

- Removed the temporary shims: `amco.model`, `engine.ollama_chat`, `engine.context_settings`, and the `storage._has_fts` re-export.
- Existing tests changed only in import, patch and call paths. No assertion or expected value changed.
- Compared CLI help and read-only command output against v0.2.0 on a copy of a real database.
- Version bumped to 0.5.0.

**Tests:** the 105 v0.2.0 tests, plus contract, adapter, configuration and architecture tests (`<N>` in total). None need Ollama.

---

## Sprint 10a — Schema versioning and safe migrations (0.6 series, in progress)

**Goal:** make schema changes safe before any 0.6 feature changes the database.

- New `storage/schema.py`: the schema version lives in `PRAGMA user_version`. Migration 1 is the old in-place upgrade, unchanged, so any 0.1 to 0.5 database reaches the same schema. The fingerprint test confirms it.
- Each migration runs under `BEGIN IMMEDIATE` with the version re-read inside the lock, and the version bump commits with the change or not at all. A failing migration rolls back.
- A database from a newer AMCO is refused with a clear message (`SchemaError`) and is not touched.
- New `storage/backup.py`: before a real upgrade, the database is copied to `<name>.bak-v<old version>` using SQLite's backup API. Backups are never overwritten, and if the backup fails the upgrade is not attempted.
- `connect()` no longer runs `PRAGMA table_info` and an `UPDATE` on every call; it reads `user_version` instead. `storage_operations.json` was regenerated for this and the diff reviewed.
- CLI commands and the chat loop report schema problems as one clear line (exit code 1) instead of a traceback.
- No new commands, no schema change, no change to retrieval.

## Current command reference

| Command | Purpose |
|---------|---------|
| `amco version` | Show the version |
| `amco init` | Create the workspace and database |
| `amco chat` | Interactive chat with Working Memory and memory retrieval |
| `amco memory add "text" [-c category] [-t type] [--confidence 0-1] [--expires DATE] [--supersedes ID] [--force]` | Save a memory (blocks exact duplicates unless `--force`) |
| `amco memory list [-t type] [--all]` | List active memories (`--all` includes superseded and expired) |
| `amco memory inspect <id>` | Show one memory in full |
| `amco memory update <id> [--content ...] [-c ...] [-t ...] [--confidence ...] [--expires DATE\|none]` | Edit a memory |
| `amco memory supersede <old-id> <new-id>` | Replace a memory with another (old one is hidden, not deleted) |
| `amco memory restore <id>` | Bring a superseded memory back |
| `amco memory review [--apply] [--yes]` | Suggest (or apply) lifecycle changes |
| `amco memory search "words" [--limit N] [--explain]` | Ranked full-text search |
| `amco memory reindex` | Rebuild the search index |
| `amco memory delete <id> [--yes]` | Delete a memory |

**Chat commands:** `/task`, `/remember`, `/why`, `/status`, `/clear`, `/help`, `/exit`

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `AMCO_DB_PATH` | `~/.amco/amco.sqlite3` | Database location |
| `AMCO_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `AMCO_MODEL` | `qwen2.5:3b` | Model name |
| `AMCO_PROVIDER` | `ollama` | Model adapter to use (only `ollama` exists so far) |
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
| `AMCO_STALE_DAYS` | `90` | Idle days before `review` suggests archiving a persistent memory |
| `AMCO_PROMOTE_USES` | `5` | Uses before `review` suggests promoting a long-term memory |
| `AMCO_SUPERSEDED_RETENTION_DAYS` | `30` | Days a superseded memory is kept before `review` suggests deleting it |

## Project structure

```
src/amco/
├── __init__.py
├── ame.py          # Adaptive Memory Engine: analysis, conflicts, budgeting, assembly
├── config.py       # All environment-based settings
├── engine.py       # Public answer() entry point (AME plus the model call)
├── lifecycle.py    # Memory review: expiry, supersession, archive, promote
├── ranking.py      # Scoring formula
├── working.py      # Working Memory and token estimation
├── cli/
│   ├── __init__.py   # Builds the app and registers the commands
│   ├── chat.py       # Chat help, command handler, and loop
│   ├── common.py     # Consoles and shared help strings
│   ├── memory.py     # The memory command group
│   └── system.py     # version and init
├── models/
│   ├── __init__.py   # get_model() factory
│   ├── base.py       # ChatModel interface, ModelError
│   └── ollama.py     # OllamaChat adapter
└── storage/
    ├── __init__.py   # Public API (re-exports)
    ├── db.py         # Connection, migration, FTS5 setup, index rebuild
    ├── hygiene.py    # Supersession and duplicate checks
    ├── memories.py   # Records, validation, CRUD, usage counts
    ├── search.py     # Retrieval and ranking entry points
    └── text.py       # Term extraction and normalization
```

```
tests/
├── snapshots/              # v0.2.0 snapshots: CLI tree, schema, storage operations
├── test_ame.py
├── test_architecture.py
├── test_cli.py
├── test_config.py
├── test_contract_cli.py
├── test_contract_imports.py
├── test_contract_imports_models.py
├── test_contract_model_payloads.py
├── test_contract_schema.py
├── test_contract_storage.py
├── test_engine.py
├── test_engine_context.py
├── test_engine_retrieval.py
├── test_hygiene.py
├── test_lifecycle.py
├── test_model.py
├── test_models.py
├── test_ranking.py
├── test_search.py
├── test_shims_removed.py
├── test_storage.py
├── test_storage_modules.py
└── test_working.py
```
## Known gaps (deferred to later sprints)

- No semantic (embedding) search; FTS5 matches words and their stems, not meaning.
- Only the Ollama adapter exists; the `ChatModel` interface is in place for other runtimes.
- No `models`, `stats`, or `config` commands, and no TOML configuration.
- No retrieval metrics or evaluation set; ranking weights are untuned defaults.
- Conflict detection is a term-overlap heuristic and cannot confirm contradictions.
- The task classifier is rule-based and English-only.
- Follow-up retrieval uses only user turns and the pinned task, not assistant replies.
- No summarization of dropped turns.
- No automatic memory evaluation; memories are saved only by explicit command (`add`, `/remember`).
- `review` does not flag near-duplicates, and confidence is set manually.
- Token counts are an estimate, not a real tokenizer.
- No backup, export, or import commands.

---

## Release 0.1.0

Sprints 1 to 3 conclude the 0.1.0 release. Sprint 4 onward belongs to the 0.2 series.

- Licensed under GPL-2.0-or-later (`LICENSE` file, SPDX and GPL notice header in every source file, license declared in `pyproject.toml`).
- Repository published on GitHub and tagged `v0.1.0`.
- Default model: `qwen2.5:3b` (4-bit quantized) via Ollama. The model has its own license, separate from AMCO's.

---

## Release 0.2.0

Sprints 4 and 5 conclude the 0.2.0 release.

- Full-text search (FTS5) with a keyword fallback, and an explainable ranking formula (relevance, confidence, freshness, usefulness).
- The Adaptive Memory Engine pipeline, with `/why` diagnostics.
- Memory hygiene (duplicates, supersession, expiry) and `amco memory review`.
- Tagged `v0.2.0`. The version string is `0.2.0`.
- **Upgrading from 0.1.x:** the database migrates automatically on first use, but the migration is one-way. Copy `~/.amco/amco.sqlite3` before upgrading if you want a rollback.

---

## Release 0.5.0

Sprints 6 to 9 conclude the 0.5.0 release: a modularization update with no change to commands, options, output text, or the database schema.

- Tagged `v0.5.0`. The version string is `0.5.0`.
- **Upgrading from 0.2.x:** no action needed. A 0.2.0 database works with 0.5.0, and the other way round.
- New setting: `AMCO_PROVIDER` (default `ollama`).
- Removed internal modules (the Python API was never documented): `amco.model` (use `amco.models.OllamaChat`), `amco.engine.ollama_chat` (use `amco.models.get_model().chat(...)`, or pass `model=` to `amco.engine.answer`), `amco.engine.context_settings` (import it from `amco.config`), and `amco.storage._has_fts` (now `amco.storage.db._has_fts`).
- Rollback point: `v0.2.0`.

---

## Up next — 0.6 series (candidates, to be confirmed)

Capability work deferred from 0.5.0:

- Automatic memory capture: proposals only, stored separately, approved by the user, screened for secrets, and checked against the duplicate and conflict logic.
- Memory maintenance improvements (near-duplicates in `review`, richer conflict handling).
- Smarter retrieval, preceded by a small benchmark so any improvement can be measured. Semantic search is kept only if it beats the FTS5 baseline.
- Coding-session support, after deciding project scoping and how code counts against the token budget.
- TOML configuration and the `stats`, `models`, and `config` commands.

Also carried over from the earlier draft: an evaluation baseline with retrieval metrics, and backup, export and import commands.

This list is a proposal, not a commitment.


