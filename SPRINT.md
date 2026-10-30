# AMCO Sprint Plan: v0.6 to v1.0

Status: planning
Last updated: 2026-10-24
Starting point: v0.5.0 (modular release, tagged)
Target: v1.0.0

---

## 1. Goal of v1.0

AMCO v1.0 is the first release where the memory system works end to end and its quality is measured, not assumed.

| Feature | Priority | v1.0 outcome |
|---|---|---|
| Memory systems | Important | Real Working, Persistent and Long-Term memory. LTM holds session summaries and archived history, with defined promote and archive rules. |
| Retrieval | Important | Hybrid FTS5 plus optional embeddings, tuned ranking, follow-ups that use assistant turns, and a better task classifier. |
| Evaluation | Important | A benchmark, `amco eval`, and metrics (recall@k, MRR, memory tokens, latency). |
| Capture | Important | Proposed memories go to an inbox, are screened for secrets, and need user approval. |
| Conflicts | Standard | Classified as update, correction, exception or unresolved, with a resolution flow. |
| Maintenance | Standard | Near-duplicates in `review`, consolidation of related memories, summaries of dropped turns. |

AMCO only has to be worth a try. A measured result slightly below the original vision is shippable. An unmeasured result is not.

### Deferred to 1.1 and later

- Multi-runtime support and `amco models`
- Project scoping (memory namespaces)
- Backup, export and import commands (only the automatic pre-migration copy is in 1.0)
- TOML configuration, `amco config` and `amco stats`
- `amco doctor`
- Local API (FastAPI) and browser dashboard
- Coding-session support, multi-user support
- Rolling in-prompt summaries of dropped turns (1.0 only summarizes dropped turns into LTM proposals)
- A SQLite vector extension or numpy-based vector search (1.0 uses plain stored vectors)

---

## 2. Versioning

| Change | Version bump |
|---|---|
| A feature series is finished and released | Minor (0.6, 0.7, 0.8, 0.9) |
| Fix only, no new features, no schema change | Patch (0.6.1) |
| Release candidate | Git tag `v1.0.0-rc.1`, written `1.0.0rc1` in `pyproject.toml` (PEP 440) |
| Final release | `1.0.0` |

- Sprints inside a version are not tagged. Each lives on its own `sprint-N` branch (CI already runs on `sprint-*`, so `sprint-12a` works too) and merges to `main`.
- `__version__` in `src/amco/__init__.py` and `version` in `pyproject.toml` change only at release time, together.
- After 1.0: patch for fixes, minor for additive features and automatic migrations, major for anything breaking.

---

## 3. Flexible sprints

- Every version lists its planned sprints plus a reserve slot.
- A sprint that grows too big is split with letter suffixes (12 becomes 12a, 12b, 12c) so numbering never shifts.
- A feature that proves larger than expected gets more sprints inside its version. A version is released when its release criteria (section 8) are met, not when the planned sprints run out.
- Every split or addition goes in the change log (section 11) with the reason.
- Only deferred scope can move between versions, and only by a recorded decision.

---

## 4. Working agreements

### 4.1 Rules for every sprint

- Every sprint produces something demonstrably working, even if small.
- Work on a `sprint-N` branch and push it first. Never commit straight to `main`.
- All code is delivered in chat with explicit where-to-edit instructions and the design reason for each choice.
- Tests pass without Ollama. The chat model and the embedder are mocked.
- CI is green on Ubuntu and Windows, Python 3.11 and 3.13, before merging.
- `DEV_PROGRESS.md` holds summaries only. Detailed records stay in the local `SPRINT.md`. README changes only when requested.
- Every new module gets an entry in `RANKS` in `tests/test_architecture.py` in the same commit. A module may import only modules with a lower rank, so give a new module a rank just above what it imports. Only relative order matters, so renumber freely.
- From Sprint 11 on, any sprint that touches retrieval or ranking runs `amco eval run` before and after, and records the difference in the sprint review.

### 4.2 Standard close-out (the last tasks of every sprint)

- [ ] `pytest` passes locally and CI is green on the branch
- [ ] Demo commands run manually and behave as described
- [ ] Acceptance criteria checked one by one
- [ ] Unfinished work written down in `SPRINT.md`
- [ ] `DEV_PROGRESS.md` gets a short summary of the sprint
- [ ] Pull request opened, reviewed against the criteria, merged to `main`

### 4.3 Planned contract changes

The 0.5.0 contract tests pin the CLI tree, the schema and the storage SQL to v0.2.0 snapshots. That was right for a refactor. From 0.6 on they change on purpose.

- Regenerate a snapshot only inside the sprint that causes the change, with the reason in the commit message.
- Read the snapshot diff before committing. Never regenerate just to get a green test.
- Rename the "v0.2.0" wording in the contract tests to the version that introduced the change.
- Sprint 10 keeps copies of the old snapshots in `tests/snapshots/legacy/`, which the Sprint 18 upgrade tests use.

### 4.4 Planned layering changes (`RANKS`)

| Sprint | New module | Imports from (must rank lower) |
|---|---|---|
| 10 | `storage.schema` | stdlib only (rank equal to `storage.text` is fine) |
| 10 | `evaluation` | `ame`, `storage`, `working`, `config` |
| 11 | `summaries` | `models`, `working`, `config` |
| 12 | `storage.vectors` | `storage.db`, `storage.memories` |
| 12 | `semantic`, `retrieval` | `storage`, `models`, `ranking`, `config` (`ame` then ranks above `retrieval`) |
| 14 | `screening` | stdlib only |
| 14 | `storage.proposals` | `storage.db`, `storage.memories`, `storage.hygiene` |
| 15 | `capture` | `screening`, `storage`, `summaries` |
| 16 | `storage.conflicts`, `conflicts` | `storage`, `storage.text`, `ranking` |

---

## 5. Ship rules for measured features

- **Embeddings (Sprint 12):** kept if not worse than the FTS5 baseline by more than a tolerance set once the baseline exists (suggested starting point: no more than 0.02 lower on overall recall@5 and MRR, and a visible gain on the paraphrase subset). If they miss, they ship optional and off by default. If they cannot be made stable on Windows and Ubuntu, they move to 1.1.
- **Tuned weights and classifier (Sprint 13):** replace current defaults only if the benchmark improves on held-out queries, not only on the queries used for tuning.
- **Capture, conflicts, maintenance:** judged by whether they work and are safe, with precision recorded. They always propose and never silently write or delete.

---

## 6. Roadmap overview

| Version | Theme | Planned sprints |
|---|---|---|
| 0.6 | Measure and structure | 10, 11, reserve |
| 0.7 | Retrieval | 12 (12a, 12b, 12c), 13, reserve |
| 0.8 | Capture | 14, 15, reserve |
| 0.9 | Conflicts and maintenance | 16, 17, reserve |
| 1.0 | Release | 18, reserve |

---

## 7. Sprint details

# v0.6: Measure and structure

## Sprint 10: Evaluation harness, schema versioning, safe migrations

**Branch:** `sprint-10`

**Objective:** make quality measurable and schema changes safe, before anything else changes.

### Design decisions (settle first)

- **D1 Fixture format.** One JSON file. Memories are referenced by a stable `key`, never a database ID.
- **D2 Where it lives.** New package `src/amco/evaluation/` (`fixtures.py`, `metrics.py`, `runner.py`, `store.py`, `report.py`) and a CLI group in `src/amco/cli/evaluation.py`.
- **D3 What is measured.** Two views per query: the ranked candidates (retrieval quality) and the memories actually selected for the prompt (what the model sees).
- **D4 Default k.** 5, which matches `DEFAULT_DEPTH`.
- **D5 Migration design.** `PRAGMA user_version` holds the schema version. Version 0 means "unversioned" (every 0.1 to 0.5 database). Migration 1 upgrades any unversioned database to the current 0.5 schema.
- **D6 Where baselines are kept.** The committed baseline result lives in `benchmarks/` in the repo. Ad hoc runs are saved under the local eval directory.

### Tasks

**Setup**
- [ ] S10-01 Create `sprint-10` from an up-to-date `main`. Run `pytest` and note the passing count (it replaces the `<N>` placeholder in DEV_PROGRESS).
- [ ] S10-02 Housekeeping: in `tests/test_storage_modules.py` the last test is indented inside `test_package_init_only_re_exports`, so pytest never collects it. Un-nest it and run it. If it fails, record why instead of fixing it in this sprint.
- [ ] S10-03 Copy `tests/snapshots/schema_fingerprint.json`, `storage_operations.json` and `cli_structure.json` into `tests/snapshots/legacy/` with a `_v0.5.0` suffix before anything is regenerated.

**Schema versioning and migrations**
- [ ] S10-04 Create `src/amco/storage/schema.py` with `SCHEMA_VERSION = 1`, an ordered `MIGRATIONS` list (version, description, function taking a connection), `current_version(conn)` and `migrate(conn)`.
- [ ] S10-05 Move the body of `db._migrate` into migration 1 unchanged. Keep the ALTER order identical (`updated_at`, `memory_type`, `confidence`, `use_count`, `superseded_by`, `superseded_at`, `expires_at`, `last_used_at`) so the fresh-database schema fingerprint stays byte-identical.
- [ ] S10-06 Rewrite `db.connect`: note whether the `memories` table already existed, create the base table if needed, read `user_version`, run pending migrations, then `_ensure_fts`. Leave `_ensure_fts` outside the numbered migrations because FTS5 availability is detected at run time and `executescript` commits implicitly.
- [ ] S10-07 Add `SchemaError` (a plain `Exception`, not `RuntimeError`, so chat does not label it a model error). If `user_version` is higher than `SCHEMA_VERSION`, raise it with a message telling the user the database was made by a newer AMCO. Re-export it from `amco.storage`.
- [ ] S10-08 Run each migration inside an explicit transaction and set `user_version` in the same transaction. Roll back on error. Prove this with a deliberately failing migration in a test (confirm `user_version` and the data are unchanged afterward).
- [ ] S10-09 Pre-migration backup: when the file existed, the `memories` table existed, and a migration is pending, copy the database with `sqlite3.Connection.backup()` to `<name>.bak-v<old version>` next to it. Never overwrite an existing backup (add a timestamp suffix instead). No copy for fresh databases or when nothing is pending.
- [ ] S10-10 Surface `SchemaError` cleanly: add a small decorator in `cli/common.py` that prints the message to `err_console` and exits with code 1, apply it to commands that open the database, and add an `except SchemaError` branch in the chat loop.

**Evaluation fixtures**
- [ ] S10-11 `evaluation/fixtures.py`: dataclasses for fixture memories, queries and the set, `load_fixtures(path=None)`, and `fixture_hash()` (sha256 of canonical JSON).
  - Memory fields: `key`, `content`, `category`, `memory_type`, `confidence`, `age_days`, `expires`, `supersedes` (a key), optional `use_count`.
  - Query fields: `id`, `query`, `expect` (list of keys, empty for negative queries), `history` (bool), `turns` (earlier chat turns to seed Working Memory), `task`, `tags`, optional `expect_kind` (classifier check), optional `split` (`train` or `dev`, used in Sprint 13).
- [ ] S10-12 Validation with clear errors: duplicate keys, empty content, unknown keys in `expect` or `supersedes`, bad types, negative `age_days`, bad dates, unknown fields.
- [ ] S10-13 Write `evaluation/fixtures/default.json` with about 30 memories and at least 40 queries across these tags: `exact`, `stem`, `multi-term`, `paraphrase` (no word overlap, expected to miss under FTS5, at least 8), `followup` (with `turns`), `history` (long-term memories plus history cues), `superseded` (the old fact must not appear), `expired`, `duplicate`, `conflict`, `negative` (nothing relevant), `chitchat`.
- [ ] S10-14 Packaging: add `[tool.setuptools.package-data]` for `evaluation/fixtures/*.json` in `pyproject.toml` and load via `importlib.resources`, so the default fixtures exist after a non-editable install.

**Metrics and runner**
- [ ] S10-15 `evaluation/metrics.py` (pure functions): `recall_at_k`, `reciprocal_rank`, `precision_at_k`, `percentile`, plus aggregation. Convention: negative queries are excluded from recall and MRR and counted in a separate `false_inclusion` rate (any memory selected when none was expected).
- [ ] S10-16 Add an optional `db_path` argument to `ame.retrieve()` and `ame.prepare()`, passed down to `search_memories`. Default behavior is unchanged. This is how the harness targets a temp database without touching the environment.
- [ ] S10-17 `evaluation/runner.py`, `build_database(fixtures, path)`: create memories with `add_memory`, resolve `supersedes` keys, and backdate `created_at` and `updated_at` from `age_days` with a documented `UPDATE` through `storage.session`. Return a `{key: id}` map.
- [ ] S10-18 `run_suite(fixtures, k, db_path=None)`: for each query create a fresh `WorkingMemory` (seed `turns` and `task`), call `ame.prepare`, map candidate and selected IDs back to keys, and record kind, memory tokens, prompt tokens, retrieval ms and total ms. Never call `ame.finish`, so `use_count` stays untouched and runs are repeatable.
- [ ] S10-19 Aggregate overall and per tag: recall@k and MRR for candidates and for selected memories, false-inclusion rate, classifier accuracy when `expect_kind` is present, mean and max memory tokens, and latency mean, p50 and p95.

**Storing and comparing runs**
- [ ] S10-20 Add `eval_dir()` to `config.py` (`AMCO_EVAL_DIR`, default `<database folder>/eval`).
- [ ] S10-21 `evaluation/store.py`: save and load runs as JSON, with a name check (`[A-Za-z0-9._-]{1,64}`, so no path traversal) and run metadata (AMCO version, Python, platform, SQLite version, FTS5 available, fixture name and hash, k, mode, ranking weights, half-life, context settings).
- [ ] S10-22 `evaluation/report.py`: Rich tables for a run and for a comparison (metric deltas plus the queries that flipped between hit and miss). `compare` refuses runs with different fixture hashes unless `--force`.

**CLI**
- [ ] S10-23 `cli/evaluation.py` with `eval run [--fixtures PATH] [--k N] [--tag TAG] [--save NAME] [--out FILE] [--verbose] [--json] [--min-recall X] [--min-mrr X]`, `eval compare A B [--force]` and `eval list`. `--verbose` shows each miss with expected keys, returned keys and ranks. The `--min-*` options exit with code 1 when a metric falls below the threshold, so CI and later sprints can gate on them.
- [ ] S10-24 Register the group in `cli/__init__.py` with `app.add_typer(eval_app, name="eval")`.
- [ ] S10-25 Add a CI smoke step after the non-editable install: run `amco eval run` (FTS only, no Ollama).

**Architecture and contracts**
- [ ] S10-26 Add `"storage.schema"` and `"evaluation"` to `RANKS`.
- [ ] S10-27 Regenerate `storage_operations.json` and `cli_structure.json` deliberately. Expect the per-connect statement list to change: `PRAGMA table_info` and the `UPDATE ... updated_at` statement no longer run on every connect, and a `PRAGMA user_version` read appears. Update `test_command_names_and_order_are_stable` for the new group and its position (read the regenerated snapshot rather than guessing the order).
- [ ] S10-28 Verify `schema_fingerprint.json` is unchanged. `user_version` lives in the database header, not in `sqlite_master`, so a changed fingerprint means a bug.
- [ ] S10-29 Update the public-surface contract tests with the new names (`SchemaError`, evaluation functions).

**Baseline and docs**
- [ ] S10-30 Run `amco eval run --save fts-baseline --out benchmarks/fts-baseline-0.6.json`. Commit the JSON. Record the headline numbers in DEV_PROGRESS.
- [ ] S10-31 Add a short "How to extend the fixtures" note to SPRINT.md.

### Tests to add

- `tests/test_eval_metrics.py`: recall, MRR and precision edge cases (empty expected, duplicates, k larger than results), percentile maths.
- `tests/test_eval_fixtures.py`: every validation error, the packaged fixtures load, every `expect` key exists, hash is stable.
- `tests/test_eval_runner.py`: a tiny fixture end to end with exact expected numbers, superseded and expired memories never returned, `use_count` untouched after a run, FTS-fallback path.
- `tests/test_eval_store.py`: save, load, compare, bad names rejected, mismatched hash refused.
- `tests/test_migrations.py`: fresh database ends at the latest version, an unversioned Sprint 1 database migrates with its data, reopening does nothing, backup created exactly once and not for fresh databases, a newer-version database raises `SchemaError`, a failing migration rolls back.
- `tests/test_cli_eval.py`: `eval run` with a tiny `--fixtures` file, `--save` and `compare`, `--min-recall` exit code.

### Acceptance criteria

1. `amco eval run` prints recall@k, MRR, tokens and latency, overall and per tag, and can save the run.
2. `amco eval compare` shows metric deltas and which queries flipped.
3. A 0.2 to 0.5 database migrates to versioned schema 1 without losing data.
4. A backup copy is made before a real migration and not when nothing changes.
5. The FTS5 baseline is committed and recorded in DEV_PROGRESS.
6. The schema fingerprint is unchanged, and the other changed snapshots were regenerated deliberately.
7. Tests pass without Ollama, and CI is green on all four combinations.

**Demo:** `amco eval run --save baseline`, then `amco eval run --verbose` and read the paraphrase misses.

**Out of scope:** embeddings, tuning, new memory columns.

---

## Sprint 11: Memory systems (a real LTM)

**Branch:** `sprint-11` (suggested split: 11a data model and retrieval, 11b lifecycle rules and model-drafted summaries)

**Objective:** turn Persistent and Long-Term memory from one type flag into two systems with different jobs and clear rules.

### Design decisions (settle first)

- **K1 Kinds.** `kind` is one of `fact` (a stable statement), `summary` (a condensation of a session or period) and `record` (a completed task or decision log). Archiving stays a tier move (`memory_type`), as in `lifecycle.apply_finding`.
- **K2 Storage.** Same `memories` table plus new columns: `kind` (NOT NULL DEFAULT `'fact'`), `source_session`, `period_start`, `period_end`. Search and ranking stay unchanged.
- **K3 Movement rules.** One table, documented in code and tested arrow by arrow:

| Move | Trigger | Who decides |
|---|---|---|
| WM to PM | `/remember` | User |
| WM to LTM | `/summary` or `/summarize` (kind `summary`) | User |
| PM to LTM | `review` archives persistent memories idle 90 days | User approves with `--apply` |
| LTM to PM | `review` promotes long-term `fact` memories used 5 or more times and still active | User approves with `--apply` |
| LTM to WM | Retrieval (history cues lift the long-term demotion) | AME |

- **K4 Promotion scope.** Summaries and records are never promoted by `review`, only by explicit `memory update --type persistent`. This keeps session summaries out of the stable-facts tier.
- **K5 Session identity.** Each `WorkingMemory` gets a `session_id` and `started_at`. `/clear` starts a new session.
- **K6 Summary tier.** Summaries and records default to `long_term`.

### Tasks

**Setup and baseline**
- [ ] S11-01 Branch from `main`. Run `amco eval run --save pre-sprint-11` as the regression reference.

**Schema and storage**
- [ ] S11-02 Add migration 2 to `storage/schema.py`: four `ALTER TABLE ... ADD COLUMN` statements. Existing rows become `kind='fact'`. The pre-migration backup from Sprint 10 should trigger automatically (verify).
- [ ] S11-03 In `storage/memories.py` add `VALID_KINDS`, `_check_kind`, the new names in `_FIELDS` (appended), and keyword arguments on `add_memory`: `kind`, `source`, `source_session`, `period_start`, `period_end`. Validate periods (a date or `YYYY-MM-DD HH:MM:SS`, start not after end). Summaries and records default to `long_term`.
- [ ] S11-04 Add `VALID_SOURCES` (`user`, `chat`, `summary`) and stop hardcoding `'user'` in the INSERT. Later sprints extend the tuple.
- [ ] S11-05 `update_memory` accepts `kind`. Re-export `VALID_KINDS` from `amco.storage`.

**Working Memory and chat**
- [ ] S11-06 `working.py`: add `session_id` (short uuid) and `started_at`, reset both in `clear()`. Extend `tests/test_working.py` without touching existing assertions.
- [ ] S11-07 `/remember` saves with `source='chat'` and the current `source_session`.
- [ ] S11-08 Add `/summary <text>` to `cli/chat.py` and `CHAT_HELP`. It saves exactly the text as an LTM `summary` with the session period. No model involved.
- [ ] S11-09 (11b) Create `src/amco/summaries.py` with `draft_summary(turns, model)`: a fixed prompt that treats the transcript as data, caps the input to the usable context, and returns a trimmed, length-limited summary or raises on empty output.
- [ ] S11-10 (11b) Add `/summarize`: draft with the model, show it, ask for approval, then save as in S11-08. Pass the summarizer into `run_chat` the same way `answer_fn` is passed, so tests can inject a fake.
- [ ] S11-11 `/status` shows the session id.

**Retrieval and prompt**
- [ ] S11-12 `ame.format_memory`: facts keep the current format exactly. Summaries and records show kind and period, for example `- [Memory 7 | summary 2026-10-20 | notes] ...`. Use `.get("kind")`, because existing tests pass memory dicts without that key.
- [ ] S11-13 `ContextReport`: add `selected_kinds` (default empty) at the end of the dataclass and print kinds for non-fact memories in `/why`.
- [ ] S11-14 Check the history path end to end: a history cue lifts the long-term demotion (`usefulness(..., history=True)`), so summaries compete fairly. Do not change ranking in this sprint. Measure first.

**Lifecycle rules (11b)**
- [ ] S11-15 `lifecycle.review`: restrict the promote rule to `kind == 'fact'` (K4). Write the movement table (K3) as the module docstring.
- [ ] S11-16 Confirm no rule deletes or archives summaries and records by idle time. Add a test that pins this.

**CLI**
- [ ] S11-17 `memory add --kind`, `memory list --kind`, `memory update --kind`, a `Kind` column in `list`, and kind, session and period lines in `inspect`. Add `KIND_HELP` to `cli/common.py`.
- [ ] S11-18 Regenerate the CLI tree snapshot and read the diff.

**Evaluation**
- [ ] S11-19 Add LTM fixtures: summaries with periods, history-cue queries, non-history queries that must not prefer summaries, tag `ltm`.
- [ ] S11-20 Re-run eval and compare with `pre-sprint-11`. Queries not tagged `ltm` must show identical results (regression gate). Record the LTM numbers.

**Contracts**
- [ ] S11-21 Regenerate `schema_fingerprint.json` and `storage_operations.json` (new columns, new INSERT and SELECT lists). Update the public-surface tests.

### Tests to add

- Migration 1 to 2 with backup. Kind and period validation. Default tier for summaries.
- `add_memory` with `source` and `source_session`, `update_memory(kind=...)`.
- `test_working.py`: session id changes on `clear()`.
- Chat: `/summary` saves the right fields, `/remember` records the session, `/summarize` with an injected fake summarizer (approve and decline paths).
- `format_memory` for each kind, including a dict without `kind`.
- Lifecycle: each movement arrow (K3), summaries never promoted or archived by idle time.
- CLI: `--kind` on add, list and update, and the `inspect` output.

### Acceptance criteria

1. A summary can be saved to LTM from chat with its source session and period.
2. A later session asking a history question retrieves that summary, and `/why` shows its kind.
3. Persistent and LTM items are distinguishable in `list`, `inspect` and `/why`.
4. Every row of the movement table is implemented and covered by a test.
5. Older databases migrate through the Sprint 10 path with a backup.
6. Eval results for non-LTM queries are identical to `pre-sprint-11`.

**Demo:** run a chat, `/summary` something, `/exit`, start a new chat, ask "what did we decide last time about X?", then `/why`.

**Release:** cut v0.6.0 using section 9.

---

# v0.7: Retrieval

## Sprint 12: Embeddings and hybrid retrieval

**Branches:** `sprint-12a`, `sprint-12b`, `sprint-12c` (split from the start, because this is the riskiest sprint)

**Objective:** add semantic retrieval behind a setting and measure it against the FTS5 baseline.

### Design decisions (settle in 12a)

- **E1 Embedding model.** Pick one through Ollama. Candidates: `nomic-embed-text` and `all-minilm` (smaller and faster). Check the model card for any task prefixes it expects, and confirm the embedding endpoint your installed Ollama version offers (the newer `/api/embed` takes a list of inputs). Decide by size, speed on your machine and the eval result.
- **E2 Vector storage.** A `memory_vectors` table with packed float32 blobs, normalized at write time so cosine similarity is a dot product. Pure Python, no numpy. Pack with an explicit byte order so a database copied between machines stays valid.
- **E3 Staleness.** Store the embedding model name, dimension and a content hash. Database triggers delete a vector when its memory is deleted or its content changes, so a stale vector can never be used.
- **E4 When to embed.** New memories are embedded best-effort at write time in hybrid mode. `memory reindex --vectors` catches everything else. Memories without a vector remain reachable through FTS.
- **E5 Fusion.** Reciprocal rank fusion (RRF) as the default, because it needs no score normalization. A weighted-sum variant is available for comparison.
- **E6 Failure.** An unreachable or missing embedder never breaks chat. Retrieval falls back to FTS and `/why` says so.

### Sprint 12a: Embedder and vector store

**Branch:** `sprint-12a`

- [ ] S12a-01 Branch from `main`. Run `amco eval run --save pre-sprint-12`.
- [ ] S12a-02 `config.py`: `embed_model_name()` (`AMCO_EMBED_MODEL`), `retrieval_mode()` (`AMCO_RETRIEVAL_MODE`, values `fts` or `hybrid`, invalid becomes `fts`), `embed_batch_size()` (`AMCO_EMBED_BATCH`), plus defaults.
- [ ] S12a-03 `models/base.py`: add the `Embedder` protocol (`name`, `embed(texts) -> list[list[float]]`). `ChatModel` stays untouched.
- [ ] S12a-04 `models/ollama_embed.py`: `OllamaEmbedder` with batching, a timeout from config, and `ModelError` messages that mirror the chat adapter ("Cannot connect to Ollama at ...", "Embedding model 'x' was not found. Run: ollama pull x", unexpected format). Keep `httpx` confined to the `models` package.
- [ ] S12a-05 `models/__init__.py`: `get_embedder()` using the same provider setting, and update `__all__` and the models contract test.
- [ ] S12a-06 Migration 3: create `memory_vectors(memory_id INTEGER PRIMARY KEY, model TEXT NOT NULL, dim INTEGER NOT NULL, vector BLOB NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)` and two triggers: delete the vector after a memory is deleted, and after its `content` is updated.
- [ ] S12a-07 `storage/vectors.py`: `pack` and `unpack` (explicit little-endian float32), `normalize`, `upsert_vector`, `memories_missing_vectors(model)`, `vector_candidates(query_vec, pool, model)` (active memories only, with a `vector_score`), `vector_stats()`, and a guard against dimension mismatches.
- [ ] S12a-08 `src/amco/semantic.py`: `embed_missing(embedder, db_path, progress=None)` (batched, skips unchanged content via the hash) and `embed_memory(memory_id, embedder)` (best effort).
- [ ] S12a-09 `memory reindex --vectors` (progress output, summary of embedded and failed counts) and best-effort embedding after `memory add` and `/remember` in hybrid mode, with a hint to run reindex if it fails.
- [ ] S12a-10 Add `tests/fakes.py` with a deterministic `FakeEmbedder`. It maps words to dimensions through a small concept table, so synonyms such as "car" and "automobile" land close together.
- [ ] S12a-11 `RANKS`: add `storage.vectors` and `semantic`. Regenerate the schema, storage-operations and CLI snapshots, and read the diffs.
- [ ] S12a-12 Tests: pack and unpack round trip and byte order, normalization, both triggers, model change invalidates vectors, missing-vector listing, reindex is idempotent, embedder error messages, dimension mismatch guard.

**Acceptance (12a):** vectors are created, stored and rebuilt on demand, stale vectors never survive an edit or delete, and nothing changes in default (`fts`) behavior. Eval results equal `pre-sprint-12`.

### Sprint 12b: Hybrid retrieval and measurement

**Branch:** `sprint-12b`

- [ ] S12b-01 Add `src/amco/retrieval.py` with a `RetrievalOptions` dataclass (`mode`, `db_path`, `weights`, `pool`, `rrf_k`). It subsumes the Sprint 10 `db_path` argument.
- [ ] S12b-02 `retrieval.candidates(analysis, options)`: FTS candidates from `search_candidates`, vector candidates from `vector_candidates`, fused by RRF into one list with a positive `match_score`, deduplicated by memory ID. Then rank once with `rank_memories`. Never rank twice.
- [ ] S12b-03 Add the weighted-sum fusion variant behind an option so the eval can compare the two.
- [ ] S12b-04 `ame.retrieve` and `ame.prepare` take the options object and call `retrieval`. Update the engine seam (`engine.answer`) to pass options through.
- [ ] S12b-05 Fallbacks: embedder unreachable, model not pulled, no vectors yet, dimension mismatch. Each falls back to FTS and adds a note.
- [ ] S12b-06 `ContextReport`: add `mode`, `embed_ms` and `notes` (all with defaults). `/why` prints the mode used and any fallback reason.
- [ ] S12b-07 `eval run --mode fts|hybrid` and `--embed-model`. The runner embeds the temp database with the real embedder (or an injected one for tests) and records the embed model name in run metadata. `compare` shows the mode difference.
- [ ] S12b-08 Check the paraphrase fixtures are not coincidentally lexical. Add more if the subset is under 8 queries.
- [ ] S12b-09 Run `amco eval compare fts-baseline hybrid` and apply the ship rule from section 5. Record the tolerance, the numbers and the decision. Set the default mode accordingly (`hybrid` default only if it clearly passes; otherwise keep `fts` default and `hybrid` opt-in).
- [ ] S12b-10 Tests with `FakeEmbedder`: RRF arithmetic, fusion dedupe, a paraphrase found only by hybrid, fallback matrix, `/why` output, eval in both modes.

**Acceptance (12b):** `hybrid` returns results, falls back to `fts` when the embedder is down, the eval reports both modes on the same fixtures, and the ship rule outcome is written down.

### Sprint 12c: Reliability and performance (reserve; use only what is needed)

**Branch:** `sprint-12c`

- [ ] S12c-01 Windows and Ubuntu parity: byte order, paths, line endings in fixtures, and CI green on all four combinations.
- [ ] S12c-02 Performance check on synthetic collections of 1k, 5k and 10k vectors: time per query for scanning and fusing. Record the numbers and the scale at which a vector extension becomes worth it (the 1.1 trigger).
- [ ] S12c-03 Cheap speedups if needed: precomputed normalization, `heapq.nlargest` for the top pool, reading vectors in one query.
- [ ] S12c-04 Reindex UX: progress, resumable after failure, batch-size guidance, timeout advice for slow machines.
- [ ] S12c-05 User-facing note: how to pull the embedding model and switch modes.

**Demo (Sprint 12):** `ollama pull <embed model>`, `amco memory reindex --vectors`, then `amco eval compare fts-baseline hybrid`.

---

## Sprint 13: Ranking, follow-ups and classifier

**Branch:** `sprint-13`

**Objective:** improve retrieval quality using the benchmark, not guesses.

### Design decisions (settle first)

- **R1 Overfitting guard.** Tag every fixture query `train` or `dev` (about 70/30). Tune on `train`, accept changes only if `dev` also improves.
- **R2 Smallest change wins.** If two settings tie on `dev`, prefer the one closest to the current defaults.
- **R3 Weak-match handling.** The OR-joined FTS query lets one shared common term pull in a weak candidate, and relevance is normalized to the best candidate in the pool, so the top hit always scores 1.0. Consider a relative cutoff, evaluated on negative and `precision@k` metrics.

### Tasks

- [ ] S13-01 Branch from `main`. Run `amco eval run --save pre-sprint-13`.
- [ ] S13-02 Failure analysis: run `eval run --verbose` and group the misses (vocabulary gap, weak relevance, ranking order, classifier skip, follow-up). Write the table in SPRINT.md.
- [ ] S13-03 Grow the fixtures with every failure pattern found, including new `negative` and `followup` cases. Keep the `train` and `dev` split balanced.
- [ ] S13-04 Thread an optional `weights` through `RetrievalOptions` into `rank_memories`, so the harness can try weights without the environment.
- [ ] S13-05 Add `amco eval tune` (or a documented script): a coarse grid over the four weights, scored on `train`, with the `dev` score reported beside it. Output the top few settings, never auto-apply.
- [ ] S13-06 Evaluate a relative relevance cutoff (drop candidates below a fraction of the best match) and a depth sweep (`DEFAULT_DEPTH` and `DEEP_DEPTH`). Report recall against memory tokens.
- [ ] S13-07 Follow-ups: extend `analyze_task` to borrow recent assistant turns as well as user turns, trimmed to a short length, with the current message's terms still first (note the 12-term query cap in `search_candidates`). Add a fixture where the topic appears only in an assistant reply.
- [ ] S13-08 Classifier: add the optional `expect_kind` labels to fixtures and report accuracy and a confusion table. Fix the misses that matter (multi-word greetings, question-like statements without `?`). Leave non-English input for 1.1 and say so.
- [ ] S13-09 Apply only the changes that pass R1 and R2. Update defaults in `config.py` and `ame.py` constants, or make the new behaviors settings if the gain is small.
- [ ] S13-10 Record a before and after table in DEV_PROGRESS (overall, per tag, `dev` only).
- [ ] S13-11 Tests: one for each classifier change, assistant-turn borrowing, the cutoff (if adopted), and `tune` output format. Existing ranking tests must keep passing. Where a default weight changes, update `test_config.py` deliberately and note it.

### Acceptance criteria

1. A before and after table of eval scores is recorded, overall and on `dev`.
2. New defaults replace old ones only if the benchmark improves on `dev`.
3. A follow-up whose topic appeared only in the assistant's reply retrieves correctly.
4. Each classifier change has a test.

**Demo:** `amco eval compare pre-sprint-13 tuned`

**Release:** cut v0.7.0 using section 9.

---

# v0.8: Capture

## Sprint 14: Proposals inbox and secret screening

**Branch:** `sprint-14`

**Objective:** a safe place for candidate memories before they become real memories.

### Design decisions (settle first)

- **P1 Separate store.** A `proposals` table, never mixed into `memories`.
- **P2 Screening.** Runs before anything is stored. High-confidence secrets (private keys, known token formats, card-like numbers that pass the Luhn check, credentials in connection strings) are blocked and not stored at all. Lower-confidence flags (password assignments, long high-entropy strings) are stored with a flag and need `--force` to approve.
- **P3 Manual path.** `memory add` and `/remember` get the same screening: warn, and require `--force` for high-confidence matches. This updates the `--force` help text.
- **P4 Rejections are remembered.** A rejected proposal's fingerprint (hash of the normalized content) stops the same candidate being proposed again.
- **P5 Provenance and confidence.** Approved proposals become memories with `source='capture'`, a link back to the proposal, and the proposal's confidence (default 0.8, editable at approval).
- **P6 Normalization.** Proposal text is collapsed to one line and length-capped (500 characters), so captured text cannot fake prompt sections with newlines.

### Tasks

**Setup and schema**
- [ ] S14-01 Branch from `main`.
- [ ] S14-02 Migration 4: `proposals(id, content, category, memory_type, kind, confidence, status, source, source_session, reason, flags, fingerprint, created_at, decided_at, memory_id)`. Status is `pending`, `approved` or `rejected` (CHECK constraint). Index on `fingerprint` and `status`.
- [ ] S14-03 Add `'capture'` to `VALID_SOURCES`.

**Screening**
- [ ] S14-04 Create `src/amco/screening.py` (stdlib only). `screen(text)` returns findings with `type`, `severity` (`block` or `flag`) and position, never the matched text. Patterns: AWS access key IDs, GitHub tokens, Slack tokens, `sk-` style API keys, PEM private key headers, JWTs, `user:password@` in URLs, Luhn-valid 13 to 19 digit numbers, `password`, `secret` and `token` assignments, and long high-entropy strings (Shannon entropy plus length).
- [ ] S14-05 Document that screening is best-effort with expected false positives and misses.
- [ ] S14-06 Make sure no message, log or exception ever includes the matched value (show only the type and a position).

**Storage**
- [ ] S14-07 Refactor `add_memory` into an internal `_insert(conn, ...)` plus the public wrapper, with no SQL change (the storage snapshot proves it). `approve_proposal` needs to insert the memory and update the proposal in one transaction.
- [ ] S14-08 `storage/proposals.py`: `create_proposal` (normalize, screen, fingerprint, skip rejected and pending duplicates), `list_proposals(status)`, `get_proposal`, `approve_proposal(id, edits, supersedes, force)`, `reject_proposal(id)`, `purge_proposals(older_than_days, status)`. Approval re-runs screening on the final text and runs `check_duplicates`.
- [ ] S14-09 Approval rules: an exact duplicate cannot be approved (the proposal is rejected with the reason), similar memories are listed with a `--supersedes` hint, and the memory insert and proposal update commit together or not at all.

**CLI**
- [ ] S14-10 `memory propose "text" [-c] [-t] [--kind] [--reason]` (manual creation, used for demos and tests), `memory proposals [--status]`, `memory approve <id> [--content TEXT] [--supersedes ID] [--force]`, `memory reject <id>`, `memory proposals --purge`.
- [ ] S14-11 Screening on `memory add` and `/remember` (P3). Regenerate the CLI snapshot and read the diff.
- [ ] S14-12 Chat: `/proposals` shows the pending count and the first few.

**Architecture and eval**
- [ ] S14-13 `RANKS`: `screening`, `storage.proposals`. Update contract tests.
- [ ] S14-14 Add a screening mini-suite to the eval fixtures: a labeled list of secret-like and benign strings, reporting detection rate and false-positive rate.

### Tests to add

- `tests/test_screening.py`: each pattern (using obviously fake values built in the test), Luhn pass and fail, benign text, and a check that findings never contain the value.
- `tests/test_proposals.py`: create, list, approve, reject, rejected fingerprint blocks re-proposal, blocked secret not stored, flagged secret needs `--force`, duplicate handling, atomic approval (simulate a failure mid-approve), edited approval, `--supersedes`, purge.
- CLI tests for the new commands and for `memory add` screening.
- A test that nothing reaches `memories` without an explicit approve.

### Acceptance criteria

1. A proposal can be created, listed, approved and rejected from the CLI.
2. Approving writes a normal memory with `source='capture'` and a link back to the proposal.
3. Likely secrets are blocked or flagged with a clear message that never prints the secret.
4. Exact duplicates are caught at approval time, and rejected candidates stay rejected.
5. Nothing reaches `memories` without an explicit approve.

**Demo:** `amco memory propose "We decided to use SQLite"`, `amco memory proposals`, `amco memory approve 1`, `amco memory search SQLite`.

---

## Sprint 15: Capture from chat, summaries of dropped turns

**Branch:** `sprint-15` (suggested split: 15a rule-based capture and eval, 15b summaries, optional 15c model-assisted extraction)

**Objective:** make capture happen during real use, still without silent writes.

### Design decisions (settle first)

- **C1 Extraction.** Rule-based first, from user turns only (assistant text can contain hallucinated "facts"). Model-assisted extraction is an optional stretch, off by default.
- **C2 Trigger.** At session end (`/exit`, end of input, Ctrl+C) and on demand with `/capture`.
- **C3 Noise cap.** At most 5 proposals per session, highest confidence first.
- **C4 Summary policy.** Setting `AMCO_CAPTURE_SUMMARY` with values `ask` (default), `auto` and `off`. Non-interactive input behaves as `off`. Summaries are model-drafted at session end only, never per turn.
- **C5 Fallback.** If the model fails, an extractive summary (first sentence of each dropped or kept user turn, length-capped) is proposed instead. If that also fails, nothing is proposed and chat still exits normally.
- **C6 Scope.** Rolling in-prompt summaries are deferred to 1.1.

### Tasks

**Setup**
- [ ] S15-01 Branch from `main`. Run `amco eval run --save pre-sprint-15` to guard retrieval against regressions.

**Working Memory**
- [ ] S15-02 `WorkingMemory`: keep a bounded buffer of dropped turns (`dropped`), filled by `trim()`, reset by `clear()`. Existing return values and counters stay the same. Add tests alongside the current `test_working.py` cases.

**Rule-based extraction**
- [ ] S15-03 `src/amco/capture.py`: `extract_candidates(turns)` returning candidates with text, kind, memory type, confidence, the rule that matched and the source turn.
- [ ] S15-04 Sentence splitting. Skip questions, requests to the assistant ("write a ..."), code blocks, and anything outside 20 to 300 characters. Deduplicate within the session.
- [ ] S15-05 Rule classes with starting confidences (to be pruned by the precision measurement): explicit instruction ("remember that", "note that", "keep in mind", 0.9), decision ("we decided", "let's go with", "we'll use", 0.7), preference ("I prefer", "I always", "from now on", "please always/never", 0.7), possessive facts ("my/our X is Y", 0.5).
- [ ] S15-06 Pipeline per candidate: screen, normalize, check against existing memories (`check_duplicates`) and rejected fingerprints, then `create_proposal` with the reason naming the rule. Apply the C3 cap.

**Chat integration**
- [ ] S15-07 In `run_chat`, run extraction at session end and on `/capture`. Print a short result ("3 proposals pending, review with `amco memory proposals`"). Wrap everything in a guard so a capture failure never breaks the exit.
- [ ] S15-08 Update `CHAT_HELP` and add `/capture`.

**Summaries of dropped turns**
- [ ] S15-09 `config.py`: `AMCO_CAPTURE_SUMMARY`, `AMCO_SUMMARY_MIN_TURNS` (default 6), and a cap on summary length.
- [ ] S15-10 At session end, if the session is long enough (kept plus dropped turns) and the policy allows, draft a summary with `summaries.draft_summary` from the Sprint 11 work, using dropped turns plus the remaining history. Create an LTM proposal (`kind='summary'`, period from `started_at` to now, session id). Handle Ctrl+C during drafting as "skip".
- [ ] S15-11 Implement the extractive fallback from C5 and test both paths.

**Evaluation**
- [ ] S15-12 Add `evaluation/fixtures/capture.json`: 10 or more sample transcripts, each user turn labeled `capture` or `ignore`, with some deliberately tricky ones (questions, requests, secrets, assistant-only facts).
- [ ] S15-13 `eval run --suite capture`: precision, recall and F1 overall and per rule class, plus proposals per session (noise). Record the numbers and prune or lower any rule class with poor precision.

**Optional stretch (15c)**
- [ ] S15-14 Model-assisted extraction behind `AMCO_CAPTURE_MODEL`: a prompt that requests a JSON list, strict parsing and validation, a hard cap, source `capture`, confidence 0.5, and the same screening and duplicate checks. A parse failure produces zero proposals, not an error. Measure it on the same transcripts and keep it only if it adds recall without hurting precision.

**Contracts**
- [ ] S15-15 `RANKS`: `capture`. Regenerate the CLI snapshot if options changed. Update the public-surface tests.

### Tests to add

- `tests/test_capture.py`: each rule class, skipped sentence types, length bounds, cap, duplicates, rejected fingerprints, screening of candidates.
- Chat tests with injected fakes: proposals appear after `/exit`, a failing extractor does not break exit, summary `ask`/`auto`/`off`, non-interactive input skips the prompt.
- `test_working.py`: dropped buffer fill, bound and reset.
- Eval suite smoke test on a tiny transcript file.

### Acceptance criteria

1. Ending a chat produces proposals, and they are shown to the user.
2. Dropped-turn summaries appear as LTM proposals under the C4 policy.
3. Capture precision on the sample transcripts is recorded, and weak rules are pruned.
4. A failed extraction or summary never loses a reply or breaks the chat.
5. Everything still passes through the Sprint 14 safeguards (screening, duplicates, rejection memory, explicit approval).
6. Retrieval eval results are unchanged from `pre-sprint-15`.

**Demo:** chat about a project decision ("we decided to use SQLite"), `/exit`, then `amco memory proposals`.

**Release:** cut v0.8.0 using section 9.

---

# v0.9: Conflicts and maintenance

## Sprint 16: Conflict classification and resolution

**Branch:** `sprint-16`

**Objective:** replace the term-overlap hint with something that can be classified, stored and resolved.

### Design decisions (settle first)

- **F1 Kinds.** `update` (newer value replaces older), `correction` (the older was wrong), `exception` (both true, one under special conditions), `unresolved` (not enough evidence).
- **F2 Detection.** Rule-based. Candidate pairs come from term similarity at or above `SIMILARITY_THRESHOLD`. Signals: differing numbers or dates in otherwise identical text, negation flips ("not", "no longer", "never"), and cue words for each kind (update: "now", "switched to", "instead", "changed to"; correction: "actually", "correction", "I meant", "wrong"; exception: "except", "unless", "only when", "for X only"). Newer timestamp and higher confidence support an update. With no cue the pair is `unresolved`.
- **F3 Complementary facts.** Overlapping memories with no differing values and no negation ("uses SQLite for storage" and "uses SQLite for search") are not conflicts and must not be flagged. The eval measures this false-positive rate.
- **F4 Storage.** A `conflicts` table, one row per pair, with a status.
- **F5 Resolution actions.** `update`: supersede the older with the newer. `correction`: supersede and raise the winner's confidence to 1.0. `exception`: keep both, record the pair so retrieval notes the relationship. `unresolved`: leave open and keep flagging it in the prompt. `dismiss`: mark as not a conflict so it is never raised again.
- **F6 Prompt wording.** Unresolved notes keep the phrase "may disagree", so `test_prepare_adds_conflict_note_to_prompt` still describes real behavior.

### Tasks

**Setup and schema**
- [ ] S16-01 Branch from `main`. Run `amco eval run --save pre-sprint-16`.
- [ ] S16-02 Migration 5: `conflicts(id, memory_a, memory_b, kind, status, similarity, reason, detected_at, resolved_at, resolution)` with a unique pair constraint (lower ID in `memory_a`), status `open`, `resolved` or `dismissed`, and a trigger that deletes a memory's conflict rows when the memory is deleted.
- [ ] S16-03 `storage/conflicts.py`: create (ignoring an existing pair, including dismissed ones), list by status, get, resolve, dismiss.

**Classification**
- [ ] S16-04 `src/amco/conflicts.py` (pure functions): `diff_terms(a, b)` separating numeric tokens from words, a negation check, cue-word matching, and `classify(a, b) -> Classification(kind, reason, confidence)`. Keep each rule small and covered by its own test.
- [ ] S16-05 `detect_for(memory_id)`: compare a memory against active memories (candidates through term overlap, limited by an inverted term index so cost stays low), classify, and store new conflicts.
- [ ] S16-06 Hook detection after `memory add` and after proposal approval, printing a one-line pointer ("Possible conflict with #4 (update): run `amco memory conflicts`").
- [ ] S16-07 `memory conflicts --scan` to check all active memories in bulk.

**Resolution flow**
- [ ] S16-08 `memory conflicts [--status open|resolved|all]` with a table of the pair, kind, reason and similarity.
- [ ] S16-09 `memory resolve <conflict-id> [--keep A|B|both] [--as update|correction|exception|dismiss]`. Without flags it prompts step by step. Flags make it scriptable. Each action applies F5 using the existing `supersede_memory` and `update_memory`, in one transaction where possible.

**Retrieval**
- [ ] S16-10 `ame.detect_conflicts` consults stored conflicts for the selected memories first, then falls back to the existing overlap heuristic for unstored pairs. Notes use the stored kind: update and correction name the preferred memory, exception describes the relationship, unresolved keeps the "may disagree" wording. Keep `MAX_CONFLICT_NOTES = 2`.
- [ ] S16-11 `ContextReport` conflicts include their kind, and `/why` prints it.

**Evaluation**
- [ ] S16-12 Add `evaluation/fixtures/conflicts.json`: labeled pairs for each kind, complementary pairs (F3), unrelated-but-similar pairs. `eval run --suite conflicts` reports classification accuracy, a confusion table and the false-positive rate on complementary pairs. Record the numbers, including honest weaknesses.

**Contracts**
- [ ] S16-13 `RANKS`: `storage.conflicts`, `conflicts`. Regenerate the schema, storage-operations and CLI snapshots, and read the diffs.

### Tests to add

- `tests/test_conflicts_rules.py`: numeric change, negation, each cue kind, complementary pair not flagged, no-cue pair is unresolved.
- Storage: unique pair, dismissed pair not re-created, trigger cleanup on delete.
- Resolution: each F5 action changes exactly the intended data and is atomic.
- AME: stored conflicts appear in notes with the right wording, the old "may disagree" test still passes.
- CLI: `conflicts`, `--scan` and `resolve` (flags and prompts).

### Acceptance criteria

1. Conflicting memories are detected and classified, with the reason shown.
2. Each resolution path changes the data as described and is tested.
3. Unresolved conflicts are still surfaced in the prompt.
4. Complementary memories are not flagged, and the measured false-positive rate is recorded.
5. Retrieval eval results are unchanged from `pre-sprint-16`.

**Demo:** add "The API timeout is 30 seconds" and "The API timeout is now 60 seconds", run `amco memory conflicts`, then `amco memory resolve 1 --as update`.

---

## Sprint 17: Near-duplicates and consolidation

**Branch:** `sprint-17` (suggested split: 17a near-duplicate findings, 17b merge proposals)

**Objective:** keep memory healthy as it grows.

### Design decisions (settle first)

- **M1 Near-duplicate threshold.** A separate setting `AMCO_NEARDUP_THRESHOLD` (suggested start 0.75, below exact and above the 0.6 "similar" warning). Tune with fixtures.
- **M2 Conflicts are not duplicates.** Pairs the Sprint 16 classifier marks as conflicting go to the conflicts flow, never to consolidation.
- **M3 Two tiers.** Tier one needs no model: the best memory (by the existing precedence of confidence, then recency, then ID) survives, and the rest are superseded. Tier two is optional: a model drafts a merged text, which becomes a proposal.
- **M4 Reversibility.** Consolidation only supersedes, never deletes. Undo is deleting the merged memory (`delete_memory` revives what it replaced) or restoring originals one by one with `restore`.
- **M5 Apply rules.** Only `review --apply` changes anything, as with the other lifecycle actions.

### Tasks

**Setup**
- [ ] S17-01 Branch from `main`.
- [ ] S17-02 `config.py`: `AMCO_NEARDUP_THRESHOLD` and a cluster size cap (default 5).

**Near-duplicate detection (17a)**
- [ ] S17-03 `lifecycle.py`: find pairs with similarity at or above the threshold that are not exact duplicates and not conflicting (M2), using an inverted term index to avoid comparing every pair.
- [ ] S17-04 Group pairs into clusters (connected components), capped by size. Pick the survivor with the existing precedence rule.
- [ ] S17-05 Emit `supersede` findings for the non-survivors with a reason such as "near-duplicate of #3 (82% similar)". Reuse `apply_finding` unchanged.
- [ ] S17-06 Show open conflicts as a count line in `review` output ("2 open conflicts: run `amco memory conflicts`"), without changing them.
- [ ] S17-07 Performance check on 2,000 synthetic memories. Record the time and keep `review` under a few seconds.

**Merge proposals (17b, optional)**
- [ ] S17-08 Extend `Finding` with a trailing `members: tuple[int, ...] = ()` field. Keep the existing positional order so `test_lifecycle.py` still passes.
- [ ] S17-09 Add a `merge` finding type. `review` can draft merged text with the model when one is available, through a fixed prompt that treats the memories as data. Without a model, merge findings are simply not produced.
- [ ] S17-10 `apply_finding` for `merge` creates a proposal (Sprint 14 inbox) with `source='consolidation'`, the member IDs in the reason, and `--supersedes` handled at approval so the originals are superseded atomically.
- [ ] S17-11 Document undo (M4) and add `amco memory unmerge <id>` only if the plain delete turns out confusing. Otherwise keep the documented behavior.
- [ ] S17-12 Add `'consolidation'` to `VALID_SOURCES`.

**Evaluation and contracts**
- [ ] S17-13 Fixtures for near-duplicates: paraphrase pairs that should group, near-miss pairs that must not, and conflicting pairs that must be excluded. Report precision and recall of grouping, with zero tolerance for wrong merges in the release gate.
- [ ] S17-14 Update lifecycle docs, `RANKS` if modules were added, and any changed snapshots.

### Tests to add

- Near-duplicate clusters (including size cap), survivor choice, exact duplicates still handled by the existing rule, conflicting pairs excluded.
- `apply_finding` for `supersede` with a near-duplicate, undo by `restore` and by deleting the survivor.
- `merge` findings with a fake model, proposal creation, atomic approval that supersedes the members.
- Nothing changes without `--apply` (CLI test).

### Acceptance criteria

1. `review` lists near-duplicates with their similarity, and conflicting pairs are excluded.
2. Consolidation supersedes the non-survivors and never deletes them.
3. A consolidation can be undone (M4) and the undo is tested.
4. Nothing changes without `--apply`.
5. Grouping precision and recall are recorded, with no wrong merges on the fixtures.

**Demo:** add two paraphrased memories, run `amco memory review`, then `amco memory review --apply`.

**Release:** cut v0.9.0 using section 9.

---

# v1.0: Release

## Sprint 18: Final evaluation, hardening and release

**Branches:** `sprint-18`, then `release-1.0` (reserve sprints 19+ only if the release candidate finds real problems)

**Objective:** verify, document and ship.

### Tasks

**Final evaluation**
- [ ] S18-01 Run every suite (`retrieval`, `capture`, `conflicts`, near-duplicate grouping, screening) and save the results as `v1.0-final`.
- [ ] S18-02 Write the full results table, from the 0.6 baseline to 1.0, into DEV_PROGRESS, plus a short honest "known limits" list.
- [ ] S18-03 Scale check: time retrieval, `review` and a conflict scan on synthetic collections (1k, 5k, 10k memories). Record the numbers and document the supported scale.

**Hardening**
- [ ] S18-04 Prompt-injection tests: a memory whose text says "ignore previous instructions" or imitates prompt sections ("Conflict notes:", a fake task line) must stay inside its own memory line. Make `format_memory` collapse internal newlines, apply the same to stored proposals, and test that no memory can create a new section in the system message.
- [ ] S18-05 Secrets: confirm screening runs on every write path (`add`, `/remember`, `propose`, `approve`, consolidation) and that no output or saved eval run contains a matched secret.
- [ ] S18-06 Failure handling review: embedder down, model down, schema newer than code, locked database, corrupt FTS index (`reindex` recovers), full disk during a backup. Each must give a clear message and never lose a reply.
- [ ] S18-07 Document retention: superseded memories (30-day default), rejected proposal fingerprints (kept, purgeable), saved eval runs, pre-migration backups (never deleted automatically), where files live, and what leaves the machine (nothing, apart from calls to the configured local Ollama server).

**Upgrade safety**
- [ ] S18-08 Upgrade tests from fixtures built with the legacy snapshots in `tests/snapshots/legacy/`: a Sprint 1 database, a 0.2 database and a 0.5 database each migrate to the final schema with data intact and a backup created.
- [ ] S18-09 Test the downgrade guard: a 1.0 database opened by a 0.5 build (simulated by `SCHEMA_VERSION`) gives the "newer AMCO" error.

**Contracts and release**
- [ ] S18-10 Regenerate and freeze all snapshots as the 1.0 contract (CLI tree, schema, storage SQL, public imports). Rename the contract-test docstrings to 1.0 wording.
- [ ] S18-11 Update README and DEV_PROGRESS (summary only): features, commands, configuration table, limits, upgrade guide, privacy notes. README changes only when you ask.
- [ ] S18-12 Bump to `1.0.0rc1` (`pyproject.toml` and `__version__`), merge, and tag `v1.0.0-rc.1`.
- [ ] S18-13 Real-use trial of the release candidate: use AMCO for your own work for a set period. Log issues. Fix only real defects and regressions (no features).
- [ ] S18-14 Bump to `1.0.0`, tag `v1.0.0`, write the GitHub release notes.

### Acceptance criteria

1. Benchmark results and known limits are written down.
2. Upgrades from 0.1 to 0.5 databases work and keep their data.
3. The contract tests describe the 1.0 interface and pass.
4. Injection and secret-handling tests pass.
5. CI is green on all four platform and Python combinations.
6. `v1.0.0` is tagged.

---

## 8. Version release criteria

| Version | Released when |
|---|---|
| 0.6.0 | Baseline recorded, schema versioned, migrations safe, LTM works and its movement rules are tested |
| 0.7.0 | Hybrid retrieval shipped or consciously deferred under the ship rule, tuned results recorded |
| 0.8.0 | Capture works from chat into the inbox, secret screening active, no silent writes |
| 0.9.0 | Conflicts classified and resolvable, `review` handles near-duplicates and consolidation |
| 1.0.0 | Sprint 18 acceptance criteria met |

---

## 9. Release checklist (every version)

- [ ] All sprints of the version merged and CI green on `main`
- [ ] Version release criteria (section 8) met
- [ ] Full `amco eval run` saved and compared with the previous release
- [ ] Upgrade tested on a copy of a real database (the automatic backup appears)
- [ ] `version` bumped in `pyproject.toml` and `src/amco/__init__.py` together
- [ ] `DEV_PROGRESS.md` summarized, README updated if requested
- [ ] Tag `vX.Y.Z` pushed and GitHub release notes written (including rollback point and any new settings)

---

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Sprint 12 (embedder, vector store, two platforms) | Could delay 0.7 | Split 12a, 12b, 12c from the start; fallback is shipping 0.7 on tuning alone and moving semantic search to 1.1 |
| Small fixture set misleads tuning | Wrong defaults | `train` and `dev` split, minimal-change rule, grow fixtures with every failure |
| 3B model unreliable for summaries and extraction | Poor capture quality | Rule-based extraction first, extractive fallback, proposals only, precision measured |
| Schema changes pile up (five migrations) | Migration bugs | Versioned migrations, transactional steps, automatic backup, legacy upgrade tests |
| Contract snapshots regenerated carelessly | Real regressions hidden | Read every snapshot diff, regenerate only in the causing sprint |
| Pure-Python vector scan too slow at scale | Slow chat in hybrid mode | Measure in 12c, document supported scale, vector extension planned for 1.1 |
| Scope creep from the deferred list | 1.0 slips | Deferred items need a recorded decision to return |

---

## 11. Change log (this plan)

| Date | Change | Reason |
|---|---|---|
| 2026-10-24 | Plan created | v0.5.0 released; scope narrowed to memory systems, retrieval, evaluation, capture, conflicts, maintenance |
| 2026-10-24 | Multi-runtime and project scoping moved to 1.1+ | Not needed for the six core features |
| 2026-10-24 | Sprint 11 (real LTM) added | Memory systems needed its own sprint |
| 2026-10-24 | Flexible sprints per version | Allows splitting heavy work such as Sprint 12 without changing scope |
| 2026-10-24 | Detailed task lists added to every sprint | Needed for sprint planning and tracking |
| 2026-10-24 | `kind` values changed to `fact`, `summary`, `record` | Archiving is already a tier move in `lifecycle.apply_finding` |
| 2026-10-24 | Consolidation undo changed to "delete the merged memory or restore originals" | `restore_memory` revives one memory at a time, while `delete_memory` revives everything the deleted memory replaced |
| 2026-10-24 | Eval harness takes `db_path` instead of setting an environment variable | `test_only_config_reads_the_environment` forbids `os.environ` outside `config.py` |
| 2026-10-24 | Sprint 12 pre-split into 12a, 12b, 12c | Riskiest sprint; split keeps each branch demonstrable |