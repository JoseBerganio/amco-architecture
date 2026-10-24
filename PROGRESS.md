# AMCO — Progress Log, v0.6 to v1.0

Record of each sprint on the road from v0.5.0 to v1.0.0: what was added, changed, fixed and tested, and what comes next.

Plan: `SPRINT.md` (local). Earlier history (Sprints 1 to 9, releases 0.1 to 0.5): `DEV_PROGRESS.md`.
Last updated: 2026-10-30

## How to use this file

- Add one section per sprint, newest at the bottom, using the same headings every time.
- Fill a sprint in as it happens. Tick the acceptance boxes only after checking them for real.
- A sprint that is split (10a, 10b) gets one section per part.
- Nothing is marked done here until `pytest` and CI back it up.
- Fixtures and snapshots are frozen per version, not permanently. A change after the freeze needs a recorded re-baseline.

## Roadmap status

| Version | Sprint | Focus | Status |
|---------|--------|-------|--------|
| 0.6 | 10a | Schema versioning, safe migrations, backup | In progress (merge pending CI) |
| 0.6 | 10b | Evaluation harness and FTS5 baseline | Not started |
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
- **Status:** Code complete, awaiting final checks and merge
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
- S10-02 housekeeping: the last test in `tests/test_storage_modules.py` was indented inside another test, so pytest never collected it. It was un-nested and run. Result: `<passed, or failed and why>`.

### Tests

New files (all run without Ollama):

- `tests/test_migrations.py` (11 tests): migrations numbered without gaps; `SchemaError` is not a `RuntimeError`; a fresh database ends at the latest version; an unversioned Sprint 1 database migrates with its data; a current-schema database without a version is just stamped; reopening applies nothing; a migration applied elsewhere is skipped; a newer database is refused and left alone; a second migration is applied and versioned; a failing migration rolls back schema, data and version; a bug in a migration rolls back and is not disguised as a `SchemaError`.
- `tests/test_backup.py` (10 tests): backup naming (plain first, timestamped after); an unversioned database is backed up with its old columns and data; no backup for a fresh database, for reopening, or for a refused newer database; each real migration gets its own backup; an existing backup is never overwritten; a failed backup stops the upgrade; a failed migration still leaves its backup; the backup is announced in the log.
- `tests/test_cli_schema.py` (12 tests): all eleven database commands report a newer database cleanly with exit code 1, and chat reports it twice (one slash command, one question) and keeps running.

Existing tests changed only in their expectations about this sprint's work: `test_architecture.py`, `test_contract_imports.py`, the `test_contract_storage.py` docstring, and the regenerated snapshot.

Total after Sprint 10a: `<N>` tests (the Sprint 10a start was `<N before>`).

### Acceptance Criteria

Tick each box only after checking it.

- [ ] A 0.2 to 0.5 database migrates to versioned schema 1 without losing data.
- [ ] A backup copy is made before a real migration and not when nothing changes.
- [ ] A database from a newer AMCO is refused with a clear message, is not modified, and gets no backup.
- [ ] A failed migration rolls back schema, data and version, and its backup remains.
- [ ] If the backup cannot be made, the upgrade is not attempted.
- [ ] Every database command and the chat loop report schema errors as one clear line, not a traceback (exit code 1 for commands).
- [ ] The schema fingerprint and the CLI tree snapshot are unchanged, and the storage-operations snapshot was regenerated deliberately with its diff reviewed.
- [ ] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13.

Demo: copy a real database, run `amco memory list` twice (a backup notice appears once, and `<name>.bak-v0` exists), then set `user_version` to 99 and run it again to see the clean error and exit code 1.

Out of scope: the evaluation harness, embeddings, new memory columns, new commands.

### What's Next

Sprint 10b — evaluation harness and FTS5 baseline (S10-11 to S10-25, S10-30, S10-31), with these decisions already made:

- Ship rule for measured changes: judged by individual queries, with no more than 1 net query lost overall. Reports show raw counts (for example `37/40`) next to any percentage.
- Fixture expiry is written as `expires_in_days` (relative), never as an absolute date.
- Fixture queries are written as they are for now. After v1.0 the set will be re-evaluated using paraphrased versions of real chat history.
- Fixtures are frozen at the end of 10b for the 0.6 version, and any later change needs a recorded re-baseline.

First step: S10-11 to S10-14 (fixture dataclasses, validation, `expires_in_days`, the default fixture file and its packaging).

Known limits carried forward from 10a, to be recorded in `SPRINT.md`:

- Backups accumulate and there is no cleanup command. Backup, export and import tooling is deferred to 1.1.
- Two processes upgrading the same database at the same instant may each write a backup (the second is timestamped). Harmless.
- The `SchemaError` message does not include the database path.
- The backup decision uses file size, so a non-empty file without a `memories` table would be backed up unnecessarily. Conservative, and accepted.