# AMCO — Progress Log, v0.6 to v1.0

Record of each sprint on the road from v0.5.0 to v1.0.0: what was added, changed, fixed and tested, and what comes next.

Plan: `SPRINT.md` (local). Earlier history (Sprints 1 to 9, releases 0.1 to 0.5): `DEV_PROGRESS.md`.
Last updated: 2026-11-12

## How to use this file

- Add one section per sprint, newest at the bottom, using the same headings every time.
- Fill a sprint in as it happens. Tick the acceptance boxes only after checking them for real.
- A sprint that is split (10a, 10b) gets one section per part.
- Nothing is marked done here until `pytest` and CI back it up.
- Fixtures and snapshots are frozen per version, not permanently. A change after the freeze needs a recorded re-baseline.

## Roadmap status

| Version | Sprint | Focus | Status |
|---------|--------|-------|--------|
| 0.6 | 10a | Schema versioning, safe migrations, backup | Done (confirm merge and green CI before ticking its boxes) |
| 0.6 | 10b | Evaluation harness and FTS5 baseline | In progress (Steps 1 and 2 of 5 committed) |
| 0.6 | 11 (11a, 11b) | Real Long-Term Memory | Not started |
| 0.7 | 12 (12a, 12b, 12c), 13 | Embeddings, hybrid retrieval, tuning | Not started |
| 0.8 | 14, 15 | Capture inbox and screening | Not started |
| 0.9 | 16, 17 | Conflicts and maintenance | Not started |
| 1.0 | 18 | Release | Not started |

---

## Sprint 10a — Schema versioning, safe migrations and backup

### Version and sprint

- **Version:** 0.6 series (release happens after Sprint 11, per `SPRINT.md`)
- **Sprint:** 10a (first half of the original Sprint 10; 10b is the evaluation harness)
- **Branch:** `sprint-10a`
- **Status:** Code complete. Acceptance boxes below are ticked only after `pytest` and CI are confirmed green on `main`.
- **Depends on:** v0.5.0 (tagged)

### Goal

Make schema changes safe before any 0.6 feature changes the database. By the end of this sprint the schema has a version, upgrades are atomic and backed up, a database from a newer AMCO is refused instead of damaged, and every command reports schema problems as one clear line instead of a traceback. Sprint 11 will add the first real migration (migration 2) on top of this.

### Added

- `src/amco/storage/schema.py`:
  - The schema version lives in `PRAGMA user_version` (a database header field, so it never changes the schema fingerprint). Version 0 means unversioned, which covers every database made by AMCO 0.1 to 0.5. `SCHEMA_VERSION` is 1.
  - `Migration` dataclass, the ordered `MIGRATIONS` list, `latest_version()`, `current_version()`, `pending()` and `migrate()`.
  - Migration 1 is the old `db._migrate` body, unchanged (same `ALTER` order), and stays idempotent so a 0.5 database that already has every column is simply stamped.
  - Each migration runs under an explicit `BEGIN IMMEDIATE`, with `user_version` re-read after the write lock is taken, so two processes can never both run the same migration. The schema change, the data change and the version bump commit together or not at all.
  - `SchemaError`, a plain `Exception` (not a `RuntimeError`, so chat never labels it a model error). Raised for a database from a newer AMCO and for a failed migration.
  - `migrate()` takes an optional `before` hook, called once and only when something is pending, before the first migration runs.
- `src/amco/storage/backup.py`: `backup_path()` and `backup_database()`.
  - Before a real upgrade, an existing database is copied with SQLite's online backup API to `<name>.bak-v<old version>` next to it.
  - An existing backup is never overwritten (a timestamp, and a counter if needed, is added to the name).
  - A partly written backup is deleted if the copy fails.
  - If the backup fails, the upgrade is not attempted and the data is untouched.
  - No backup for fresh databases, for up-to-date databases, or for a database that is refused.
  - The user is told through a `logging` WARNING, which Python prints as one plain line on stderr when logging is not configured.
- `handle_schema_errors` decorator in `src/amco/cli/common.py`. It prints the error to stderr and exits with code 1. Applied to `init` and all ten `memory` commands.
- `SchemaError` branches in the chat loop, for both slash commands and answers.
- `SCHEMA_VERSION` and `SchemaError` exported from `amco.storage`.
- `tests/snapshots/legacy/`: copies of the v0.5.0 `schema_fingerprint.json`, `storage_operations.json` and `cli_structure.json` (S10-03), kept for the upgrade tests in Sprint 18.
- `*.sqlite3.bak-*` added to `.gitignore`.

### Changed

- `storage/db.py`: `_migrate` removed. `connect()` now creates the base table, calls `migrate()` with a backup hook, then ensures the FTS index. It no longer runs `PRAGMA table_info` and an `UPDATE` on every call; it reads `user_version` instead. The connection is now closed if the upgrade is refused or fails, so nothing leaks.
- `tests/snapshots/storage_operations.json` regenerated on purpose, because the per-connection SQL changed. The diff was read before committing: only the connection preamble moved, and every operation-specific statement and every connection count was unchanged.
- `tests/test_contract_storage.py`: docstring updated to say it is regenerated only inside the sprint that changes storage SQL, and to name this sprint.
- `tests/test_architecture.py`: `storage.schema` and `storage.backup` added to `RANKS` (rank 2, standard library only).
- `tests/test_contract_imports.py`: public surface extended with `SCHEMA_VERSION`, `SchemaError`, and the `schema` and `backup` module names.
- Unchanged on purpose: the CLI command tree (`cli_structure.json`), the database schema (`schema_fingerprint.json`), all commands, options and output text, and retrieval behavior.
- `DEV_PROGRESS.md` received a short Sprint 10a summary.

### Fixed

- A connection could have leaked if a schema upgrade failed. `connect()` now closes it before re-raising.
- S10-02 housekeeping: the last test in `tests/test_storage_modules.py` was indented inside another test, so pytest never collected it. It was un-nested and run.

### Tests

New files (all run without Ollama):

- `tests/test_migrations.py` (11 tests): migrations numbered without gaps; `SchemaError` is not a `RuntimeError`; a fresh database ends at the latest version; an unversioned Sprint 1 database migrates with its data; a current-schema database without a version is just stamped; reopening applies nothing; a migration applied elsewhere is skipped; a newer database is refused and left alone; a second migration is applied and versioned; a failing migration rolls back schema, data and version; a bug in a migration rolls back and is not disguised as a `SchemaError`.
- `tests/test_backup.py` (10 tests): backup naming (plain first, timestamped after); an unversioned database is backed up with its old columns and data; no backup for a fresh database, for reopening, or for a refused newer database; each real migration gets its own backup; an existing backup is never overwritten; a failed backup stops the upgrade; a failed migration still leaves its backup; the backup is announced in the log.
- `tests/test_cli_schema.py` (12 tests): all eleven database commands report a newer database cleanly with exit code 1, and chat reports it twice (one slash command, one question) and keeps running.

Existing tests changed only in their expectations about this sprint's work: `test_architecture.py`, `test_contract_imports.py`, the `test_contract_storage.py` docstring, and the regenerated snapshot.

### Acceptance Criteria

- [ ] A 0.2 to 0.5 database migrates to versioned schema 1 without losing data.
- [ ] A backup copy is made before a real migration and not when nothing changes.
- [ ] A database from a newer AMCO is refused with a clear message, is not modified, and gets no backup.
- [ ] A failed migration rolls back schema, data and version, and its backup remains.
- [ ] If the backup cannot be made, the upgrade is not attempted.
- [ ] Every database command and the chat loop report schema errors as one clear line, not a traceback (exit code 1 for commands).
- [ ] The schema fingerprint and the CLI tree snapshot are unchanged, and the storage-operations snapshot was regenerated deliberately with its diff reviewed.
- [ ] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13.

### What's Next

Sprint 10b (see the next section). The decisions recorded at the end of 10a (ship rule, `expires_in_days`, fixtures frozen per version) were carried out as planned.

---


## Sprint 10b — Evaluation harness and FTS5 baseline

### Version and sprint

- **Version:** 0.6 series
- **Sprint:** 10b (second half of the original Sprint 10)
- **Branch:** `sprint-10b`
- **Status:** In progress. Steps 1 and 2 of 5 are committed. Steps 3 to 5 are not started.
- **Depends on:** Sprint 10a

### Goal

Make retrieval quality measurable before anything else changes it. By the end of this sprint `amco eval run` reports recall@k, MRR, tokens and latency on a fixed benchmark, runs can be saved and compared, and an FTS5 baseline is committed in `benchmarks/`.

### Delivery plan

| Step | Tasks | Result | Status |
|------|-------|--------|--------|
| 1 | S10-11 to S10-14 | Fixtures load, validate and package | Committed |
| 2 | S10-15, S10-16 | Pure metrics; `db_path` on the AME | Committed |
| 3 | S10-17 to S10-19 | `build_database()` and `run_suite()` produce numbers | Not started |
| 4 | S10-20 to S10-22 | Store, compare, report | Not started |
| 5 | S10-23 to S10-25, S10-27, S10-30, S10-31 | `amco eval` CLI, CI smoke step, committed baseline | Not started |

### Added

**Step 1: fixtures**

- `src/amco/evaluation/` package, built as three small modules plus the public `__init__`:
  - `fixture_types.py`: frozen dataclasses (`FixtureMemory`, `FixtureQuery`, `FixtureTurn`, `FixtureSet`), `FixtureError`, and a closed set of 13 tags (`KNOWN_TAGS`), so a typo cannot silently drop a query from its report.
  - `fixture_parse.py`: pure validation. It collects every problem and reports them together with locations such as `queries[7] (id 'hist-02')`. It also rejects labels that can never be satisfied: expecting a superseded or expired memory, `supersedes` pointing at a memory defined later, two memories superseding the same one, a `negative` or chitchat query that expects memories.
  - `fixtures.py`: `load_fixtures()` (packaged default or a path, BOM-tolerant), `canonical_json()` and `fixture_hash()`. The hash covers memories and queries only, so editing the name or description never invalidates saved runs.
- `src/amco/evaluation/datasets/default.json`: 30 memories and 47 queries (14 `dev`, about 30%), 10 paraphrase queries, all 12 required tags plus `assistant-followup`. Two deliberate known misses: `follow-05` (topic only in an assistant reply) and `chat-04` ("okay cool").
- New optional query field `forbid`: keys that must not be selected, so the `superseded`, `expired` and `duplicate` cases can assert absence.
- `expires_in_days` (relative) replaces absolute expiry dates, so fixtures never rot.
- `train`/`dev` split assigned now, before any results exist.
- `pyproject.toml`: `[tool.setuptools.package-data]` so the dataset exists after a non-editable install.
- `tests/test_architecture.py`: `evaluation` added to `RANKS` at rank 9.

**Step 2: metrics and `db_path`**

- `src/amco/evaluation/metrics.py` (standard library only, enforced by a test): `recall_at_k`, `is_hit`, `reciprocal_rank`, `precision_at_k`, `forbidden_hits`, `has_false_inclusion`, `percentile` (linear interpolation), `mean_defined`, `describe`, and the `Ratio` type, which always prints raw counts, for example `37/47 (78.7%)`.
- Conventions: undefined metrics are `None`, so negative queries drop out of averages; a hit needs every expected key in the top k; precision divides by results returned, not by k; repeated keys count once.
- `ame.retrieve()` and `ame.prepare()` accept an optional trailing `db_path`, passed to `search_memories`. This is how the harness will target a temporary database without touching the environment.

### Changed

- `src/amco/ame.py`: `from pathlib import Path` added; `retrieve()` and `prepare()` gained `db_path`. Nothing removed, no new SQL.
- `src/amco/evaluation/__init__.py`: re-exports the fixture and metrics names.
- Unchanged on purpose: the CLI command tree, the schema fingerprint, the storage-operations snapshot, `engine.answer()`, and all retrieval behavior.

### Fixed

- Nothing fixed in this sprint so far.

### Tests

New files (all run without Ollama):

- `tests/test_eval_fixtures.py` (`<N>` tests): packaged dataset present and declared in `pyproject.toml`; planned size and tag coverage; train/dev split near 30%; paraphrase queries share no crudely stemmed terms with their targets; hash is stable and ignores name and description; hash changes with content; defaults and stripping; a 23-case validation matrix; two-memories-superseding-one; every problem reported at once; BOM, missing and malformed files; errors name the file.
- `tests/test_eval_metrics.py` (`<N>` tests): standard-library-only guard; recall, hit, reciprocal rank and precision edge cases (empty expectations, k larger than results, repeated keys, invalid k); forbidden hits and false inclusion; `Ratio` formatting; percentile maths and `describe`.
- `tests/test_ame_db_path.py` (5 tests): the given database is used and the configured one is never opened; `retrieve` accepts `db_path`; chitchat still skips retrieval; `prepare` alone never counts usage; default behavior unchanged.

Existing tests changed: only `tests/test_architecture.py` (one new `RANKS` entry).

Fixture hash of `default.json` at Step 1: `<12 hex chars from the verify command>`.
Passing test count after Step 2: `<N>`.

### Acceptance Criteria

- [ ] `amco eval run` prints recall@k, MRR, tokens and latency, overall and per tag, and can save the run. *(Step 5)*
- [ ] `amco eval compare` shows metric deltas and which queries flipped. *(Steps 4 and 5)*
- [ ] The FTS5 baseline is committed in `benchmarks/` and its headline numbers are recorded here. *(Step 5)*
- [ ] The schema fingerprint is unchanged, and the CLI and storage snapshots were regenerated deliberately with diffs reviewed. *(Step 5 for the CLI snapshot)*
- [ ] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13.
- [x-when-verified] Fixtures load, validate and survive a non-editable install. *(Step 1: tick after the packaging check in a clean venv)*
- [x-when-verified] `db_path` works and the storage, CLI and schema contract snapshots are unchanged. *(Step 2: tick after running the three contract tests with no regeneration)*

### Decisions made in this sprint

- Ship rule: judged by individual queries, no more than 1 net query lost overall, raw counts beside percentages.
- Labels are my reading of the code, not ground truth. When the first run appears in Step 3, each surprising hit or miss is decided explicitly as a real weakness (keep the label) or a wrong label (fix and record), before the freeze.
- `ContextReport.candidates` holds at most `limit + 3` entries and is taken before duplicate removal, so the runner computes candidate metrics and selected-memory metrics separately and applies `forbid` only to the selected view.
- `conflict-01` and `conflict-02` need both memories in the top k. Check per-query recall before concluding retrieval is broken.
- Fixtures are frozen at the end of 10b for 0.6.

### What's Next

Step 3 (S10-17 to S10-19): `build_database()` with the backdating `UPDATE` and a key-to-ID map, `run_suite()` that creates a fresh Working Memory per query and never calls `ame.finish`, and aggregation overall and per tag. First real recall and MRR numbers appear here, along with the first look at which labels were wrong.


Temporarily Stopped. No. 6 of Step 5 is yet to be implemented.