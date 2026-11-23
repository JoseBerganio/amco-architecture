# AMCO — Progress Log, v0.6 to v1.0

Record of each sprint on the road from v0.5.0 to v1.0.0: what was added, changed, fixed and tested, and what comes next.

Plan: `SPRINT.md` (local). Earlier history (Sprints 1 to 9, releases 0.1 to 0.5): `DEV_PROGRESS.md` (legacy, frozen, never edited again).
Last updated: 2026-11-22

## How to use this file

- Add one section per sprint, newest at the bottom, using the same headings every time.
- Fill a sprint in as it happens. Tick the acceptance boxes only after checking them for real.
- A sprint that is split (10a, 10b) gets one section per part.
- Nothing is marked done here until `pytest` and CI back it up.
- Fixtures and snapshots are frozen per version, not permanently. A change after the freeze needs a recorded re-baseline.

## Roadmap status

| Version | Sprint | Focus | Status |
|---------|--------|-------|--------|
| 0.6 | 10a | Schema versioning, safe migrations, backup | Done |
| 0.6 | 10b | Evaluation harness and FTS5 baseline | Done |
| 0.6 | 11a | Real LTM: data model, chat commands, retrieval, CLI, LTM fixtures | In progress |
| 0.6 | 11b | LTM lifecycle rules and model-drafted summaries | Not started |
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

- [x] A 0.2 to 0.5 database migrates to versioned schema 1 without losing data.
- [x] A backup copy is made before a real migration and not when nothing changes.
- [x] A database from a newer AMCO is refused with a clear message, is not modified, and gets no backup.
- [x] A failed migration rolls back schema, data and version, and its backup remains.
- [x] If the backup cannot be made, the upgrade is not attempted.
- [x] Every database command and the chat loop report schema errors as one clear line, not a traceback (exit code 1 for commands).
- [x] The schema fingerprint and the CLI tree snapshot are unchanged, and the storage-operations snapshot was regenerated deliberately with its diff reviewed.
- [x] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13. (confirm on the 10b merge commit)


### What's Next

Sprint 10b (see the next section). The decisions recorded at the end of 10a (ship rule, `expires_in_days`, fixtures frozen per version) were carried out as planned.

---


## Sprint 10b — Evaluation harness and FTS5 baseline

### Version and sprint

- **Version:** 0.6 series
- **Sprint:** 10b (second half of the original Sprint 10)
- **Branch:** `sprint-10b`
- **Status:** Done. Merged to `main`; CI green on all four combinations.
- **Depends on:** Sprint 10a

### Goal

Make retrieval quality measurable before anything else changes it. By the end of this sprint `amco eval run` reports recall@k, MRR, tokens and latency on a fixed benchmark, runs can be saved and compared, and an FTS5 baseline is committed in `benchmarks/`.

### Delivery plan

| Step | Tasks | Result | Status |
|------|-------|--------|--------|
| 1 | S10-11 to S10-14 | Fixtures load, validate and package | Done |
| 2 | S10-15, S10-16 | Pure metrics; `db_path` on the AME | Done |
| 3 | S10-17 to S10-19 | `build_database()` and `run_suite()` produce numbers | Done |
| 4 | S10-20 to S10-22 | Run store, comparison, reports | Done |
| 5a | S10-23 to S10-25, S10-27, S10-29 | `amco eval` CLI, gates, CI smoke step, CLI snapshot | Done |
| Review | | Label review of the first real run | Done, no label changes |
| 5b | S10-30, S10-31 | Committed baseline, freeze tests | Done |

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

**Step 3: database builder, runner, scoring**

- `build.py`: `build_database()` creates memories through `add_memory`, resolves `supersedes` keys, then runs one `UPDATE` to backdate `created_at` and `updated_at` and set `use_count`. Expiry dates are computed in UTC. A database that already holds data is refused.
- `runner.py`: `run_suite()` gives each query a fresh `WorkingMemory` seeded from the fixture, calls `ame.prepare`, and never calls `ame.finish` or the model, so runs are repeatable and `use_count` is untouched. `tags` filters queries only. Temporary database unless a path is given.
- `results.py` (data), `scoring.py` and `aggregate.py` (pure). Candidates are judged in the top k; selected memories are judged whole; `forbid` applies to the selected view only. Summaries overall, per tag and per split.

**Step 4: run store, comparison, reports**

- `config.py`: `eval_dir()` (`AMCO_EVAL_DIR`) and `set_amco_variables()` (names only, never values).
- `run_record.py`, `metadata.py`, `serialize.py`, `store.py`: runs are saved as JSON with per-query results; summaries are recomputed on load. Metadata records every setting that can change the numbers. Saves are atomic, UTF-8, LF. Run names match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.
- `compare.py`: metric deltas, flips in four views (candidates, selected, forbid, noise), settings differences, and the ship rule on both hit views. Different fixture hashes are refused unless forced.
- `report.py`: Rich tables built from `Text` cells, so query text is never read as markup. `--verbose` lists each query needing attention with found-counts.
- Fixture parser rule: `turns` must start with a user turn.

**Step 5: CLI, CI, baseline**

- `cli/evaluation.py` and `evaluation/gates.py`: `amco eval run | compare | list` (flags in SPRINT.md S10-23). Only `FixtureError` and `RunError` become one-line errors.
- CI: smoke step on the non-editable install (packaged dataset, FTS only, no Ollama, no thresholds).
- `benchmarks/fts-baseline-0.6.json`, `.gitattributes` (LF for `benchmarks/*.json`), and `tests/test_eval_baseline.py`.

### Changed

- `src/amco/ame.py`: `from pathlib import Path` added; `retrieve()` and `prepare()` gained `db_path`. Nothing removed, no new SQL.
- `src/amco/evaluation/__init__.py`: re-exports the fixture and metrics names.
- Unchanged on purpose: the CLI command tree, the schema fingerprint, the storage-operations snapshot, `engine.answer()`, and all retrieval behavior.
- `src/amco/config.py`: two functions added at the end.
- `src/amco/cli/__init__.py`: registers the `eval` group.
- `tests/snapshots/cli_structure.json`: regenerated deliberately; the diff only added the `eval` group. Storage and schema snapshots untouched.
- `tests/test_contract_cli.py`, `tests/test_contract_imports.py`: renamed and extended for the new surface.
- `.github/workflows/ci.yml`: evaluation smoke step.
- Fixture dataset: `para-09` reworded (see Fixed).

### Fixed

- `para-09` was not a real paraphrase: the FTS5 index covers `category` as well as `content`, so "legal" matched the `license` memory. The query was reworded and the guard test now includes category. It was found by tracing the code before any baseline existed, so no re-baseline was needed.

### Tests

New files, all run without Ollama: `test_eval_fixtures`, `test_eval_metrics`, `test_ame_db_path`, `test_eval_scoring`, `test_eval_aggregate`, `test_eval_build`, `test_eval_runner`, `test_eval_config`, `test_eval_metadata`, `test_eval_serialize`, `test_eval_store`, `test_eval_compare`, `test_eval_report`, `test_eval_gates`, `test_cli_eval`, `test_eval_dataset_design`, `test_eval_baseline`.

Notable guards: metrics are standard-library-only; the configured database is never created by a run; the 10 paraphrase queries cannot reach their targets (real retrieval, whole candidate pool); the dataset hash must match the newest FTS baseline; current retrieval must meet the ship rule against it.

Existing tests changed: `test_architecture.py` (one `RANKS` entry), `test_contract_cli.py`, `test_contract_imports.py`.

Passing test count at the end of 10b: `<N>`.


### Baseline (committed)

File: `benchmarks/fts-baseline-0.6.json`. Dataset hash `12b8330f241d`, k=5, FTS5 on, no `AMCO_*` settings, made from commit `<short hash>`.

| Measure | Result |
|---|---|
| Candidate hits | 27/38 (71.1%) |
| Candidate recall / MRR | 0.711 / 0.711 |
| Selected hits | 27/38 (71.1%) |
| Selected precision | 0.598 |
| Classifier matches label | 16/17 (94.1%) |
| Forbidden memories selected | 0/4 |
| Selected when nothing expected | 0/9 |
| History cues match label | 47/47 |
| Latency (retrieval p50 / p95) | about 3.5 ms / 7.8 ms |

Per tag: everything lexical is perfect on hits (`exact`, `stem`, `multi-term`, `history`, `superseded`, `duplicate`, `conflict`). All 11 misses are semantic or follow-up: `paraphrase` 0/10, `assistant-followup` 0/1. `multi-term` selected precision is only 0.275.

Label review of the first real run: 12 of 47 queries needed attention, 0 labels changed.

| Queries | Verdict | Owner |
|---|---|---|
| para-01 to para-05, para-07 to para-09 | Real weakness: no shared words, as designed | Sprint 12 (embeddings) |
| para-06, para-10 | Real weakness: retrieve unrelated memories by an incidental word ("text" in "full-text", "lives" and "live") | Sprints 12 and 13 (relative cutoff) |
| follow-05 | Real weakness: topic only in an assistant reply | Sprint 13 (S13-07) |
| chat-04 | Real weakness: classifier says `statement`, label says `chitchat` | Sprint 13 (S13-08) |

### Acceptance Criteria

- [x] `amco eval run` prints recall@k, MRR, tokens and latency, overall and per tag, and can save the run.
- [x] `amco eval compare` shows metric deltas and which queries flipped.
- [x] The FTS5 baseline is committed in `benchmarks/` and its headline numbers are recorded above.
- [x] The schema fingerprint is unchanged, and the CLI snapshot was regenerated deliberately with its diff reviewed.
- [x] Fixtures load, validate and survive a non-editable install.
- [x] `db_path` works and the storage, CLI and schema contract snapshots are otherwise unchanged.
- [x] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13. (confirm on the merge commit, including the new smoke step on Windows)

### Decisions made in this sprint

- Ship rule: judged by individual queries, at most 1 net query lost, raw counts beside percentages. Applied to both hit views (candidates and selected). `forbid` and `noise` flips are reported but excluded from the net.
- Labels are a reading of the code, not ground truth. The first real run was reviewed query by query before the baseline: no label changes.
- Candidate metrics are cut at k and judged on the candidate pool (depth + 3, before duplicate removal); selected metrics judge the whole prompt list.
- Fixtures are frozen for 0.6. Re-baselining means adding a newer file to `benchmarks/` and a change-log entry. Sprint 11 will do this when it adds `ltm` queries.
- `amco_version` stays `0.5.0` on branches, so runs should be saved with `--note "<git short hash>"`.
- A baseline contains timings, so git diffs of baselines are noisy. Decisions use hits, never milliseconds.
- `--check` is only as strong as 47 queries: one lost query is about 2 points. A net loss of 1 passes the rule but should prompt reading the flip list.
- CI thresholds (`--min-recall`, `--min-mrr`) are not set yet. Suggested: about 10 points below the baseline.

### What's Next
Sprint 11a (see below). First step: branch from `main`, save `amco eval run --save pre-sprint-11`, then migration 2.


---

## Sprint 11a — Long-Term Memory: data model, chat commands, retrieval, CLI

### Version and sprint

- **Version:** 0.6 series (v0.6.0 is released after Sprint 11b)
- **Sprint:** 11a (first half of Sprint 11; 11b is lifecycle rules and model-drafted summaries)
- **Branch:** `sprint-11a-ltm-data-model`
- **Status:** In progress
- **Depends on:** Sprint 10b (merged)

### Goal

Turn Persistent and Long-Term memory from one type flag into two systems with different jobs. By the end of this sprint a session summary can be saved to LTM from chat with its session and period, a later session asking a history question retrieves it, and `/why`, `list` and `inspect` show what kind of memory it is.

### Delivery plan

| Step | Tasks | Result | Status |
|------|-------|--------|--------|
| 1 | S11-01 to S11-05, S11-02a | Migration 2 and the storage API (`kind`, `source`, session, period) | Done |
| 2 | S11-06 to S11-08, S11-08a, S11-11, S11-15, S11-16 | Sessions in Working Memory; `/remember` records the session; `/summary` with a size check; `/status`; lifecycle never moves summaries or records by rule | Done |
| 3 | S11-12 to S11-14 | `format_memory`, `ContextReport`, history path check | Not started |
| 4 | S11-17, S11-18 | CLI `--kind`, `Kind` column, `inspect` lines, `--type` default, CLI snapshot | Not started |
| 5 | S11-19 to S11-21 | LTM fixtures, new baseline, regression gate, contracts, close-out | Not started |

### Added

**Step 1: storage foundation**

- Migration 2 in `storage/schema.py`: `kind` (NOT NULL DEFAULT 'fact'), `source_session`, `period_start`, `period_end`. It adds only the columns that are missing, so it is idempotent. Existing rows become facts.
- `VALID_KINDS` (`fact`, `summary`, `record`) and `VALID_SOURCES` (`user`, `chat`, `summary`), exported from `amco.storage`.
- `add_memory(kind, source, source_session, period_start, period_end)`: kind and source are validated; periods accept a date or a timestamp, a date-only end runs to the end of that day, and start after end is rejected.
- `update_memory(kind=...)`. Changing the kind never changes the tier.
- `tests/test_ltm_storage.py`.

**Step 2: sessions, `/summary` and the lifecycle guard**

- `WorkingMemory.session_id` (8 hex characters) and `started_at` (UTC, the format storage reads), created with the object and replaced by `clear()`. New public helper `utc_stamp()` in `working.py`.
- `src/amco/summaries.py` (rank 2, imports only `working`): `summary_limit()` and `check_summary()`. A summary may use at most half of the effective memory budget, and its whitespace is collapsed to one line.
- Chat command `/summary <text>`: saves the user's own text as a long-term summary (category `session`, source `chat`, session id, session period). No model involved. Exact duplicates are refused.
- `/status` shows the session id; `/clear` announces the new session.
- Movement-rules table (K3) as the `lifecycle.py` module docstring.

### Changed

**Step 1**

- `add_memory(memory_type=None)` now resolves the tier from the kind: summaries and records are long-term, facts persistent, and an explicit type wins. The positional order of the existing parameters is unchanged.
- The INSERT takes the source as a parameter instead of the hardcoded `'user'`.
- `schema_fingerprint.json` and `storage_operations.json` regenerated on purpose; the diffs were read first. The CLI tree snapshot is unchanged.
- `test_contract_schema.py` and `test_contract_storage.py`: wording updated to "the current schema".
- Surface tests extended with `VALID_KINDS` and `VALID_SOURCES`.


**Step 2**

- `/remember` records source `chat` and the session id. Its logic moved into a small helper in `cli/chat.py`, with unchanged behavior otherwise.
- `lifecycle.review()` applies the archive and promote rules to facts only (K11). Expiry and supersession cleanup still apply to every kind.
- `RANKS` and the public-surface test gained `summaries` and `utc_stamp`.
- No snapshot changed: no storage SQL, schema or Typer command changed.

### Fixed

**Step 1**

- `test_migrations.py` and `test_backup.py` appended `Migration(2, ...)` and asserted `user_version == 1`. That only held while migration 1 was the last one. They now use `SCHEMA_VERSION` and `SCHEMA_VERSION + 1`, so adding real migrations no longer breaks them.


**Step 2**

- Found in design review, before any code: an idle persistent summary the user had promoted would have been archived again by `review`, undoing an explicit decision. Fixed by the K11 guard.


### Tests

**Step 1**

New: `tests/test_ltm_storage.py` (defaults and the tier rule; kind, source and period validation; session and period storage; `update_memory(kind=...)`; search and list results carry the new fields; a version 1 database upgrades with its data and one backup; an unversioned 0.5 database gets exactly one backup for both migrations; a fresh database has the columns and no backup).
Changed: `test_migrations.py`, `test_backup.py`, `test_contract_imports.py`, `test_storage_modules.py`, `test_contract_schema.py` (names and docstring), `test_contract_storage.py` (docstring).
Passing test count at the end of Step 1: `<N>`.


**Step 2**

New: `tests/test_summaries.py` (limit arithmetic, whitespace collapsing, empty and oversize summaries), `tests/test_cli_chat_ltm.py` (session in `/status` and `/clear`, `/remember` source and session, `/summary` fields, usage message, size refusal, duplicate refusal, help).
Extended: `tests/test_working.py` (session id and start time, `clear()` starts a new session, the start time is a valid memory period), `tests/test_lifecycle.py` (an idle persistent summary is never archived, a well-used long-term summary or record is never promoted, an expired summary is still flagged for deletion).
Passing test count at the end of Step 2: `<N>`.

### Acceptance Criteria

- [ ] A summary can be saved to LTM from chat with its source session and period.
- [ ] A later session asking a history question retrieves that summary, and `/why` shows its kind.
- [ ] Persistent and LTM items are distinguishable in `list`, `inspect` and `/why`.
- [ ] Older databases migrate through the Sprint 10 path with a backup.
- [ ] Eval results for non-LTM queries show no flips against `pre-sprint-11`.
- [ ] Tests pass without Ollama, and CI is green on all four combinations.

### Decisions made in this sprint

**Step 1**

- `kind` has no SQL CHECK constraint; Python validates it, as it does for `memory_type`.
- Periods are descriptive metadata. They are validated but not used in ranking.
- The CLI `--type` default is still "persistent". It becomes none in Step 4 (K8), so until then `memory add` cannot create a long-term summary by default.
- The Step 1 review raised three weaknesses. How each was resolved is recorded in Step 2 below.


**Step 2**

- K11: only facts move by rule. K12: `/summary` uses category `session`, because FTS5 indexes the category and a category like `summary` would make every query containing that word match every summary. K13: a summary may use at most half of the effective memory budget, because an oversize memory is skipped by the token budget and never truncated, so it would be saved and then silently never retrieved. K14: the regression gate for the changed fixture hash is built in Step 5.
- Known gap, deferred to S18-04: `/remember` and `memory add` have no size check.
- Nothing unexpected appeared in testing: all tests were green and the model behaved as expected.


### What's Next

Steps 3 to 5 (see SPRINT.md): how summaries appear in the prompt and in `/why`, the CLI `--kind` options, and the LTM fixtures with a new baseline and the regression gate.