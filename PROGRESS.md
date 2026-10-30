# AMCO — Progress Log, v0.6 to v1.0

Record of each sprint on the road from v0.5.0 to v1.0.0: what was added, changed, fixed and tested, and what comes next.

Plan: `SPRINT.md` (local). Earlier history (Sprints 1 to 9, releases 0.1 to 0.5): `DEV_PROGRESS.md`.
Last updated: 2026-10-29

## How to use this file

- Add one section per sprint, newest at the bottom, using the same headings every time.
- Fill a sprint in as it happens. Tick the acceptance boxes only after checking them for real.
- A sprint that is split (10a, 10b) gets one section per part.
- Nothing is marked done here until `pytest` and CI back it up.

## Roadmap status

| Version | Sprint | Focus | Status |
|---------|--------|-------|--------|
| 0.6 | 10a | Schema versioning, safe migrations, backup | Done (summary in `DEV_PROGRESS.md`) |
| 0.6 | 10b | Evaluation harness and FTS5 baseline | **Planned, not started** |
| 0.6 | 11 (11a, 11b) | Real Long-Term Memory | Not started |
| 0.7 | 12 (12a, 12b, 12c), 13 | Embeddings, hybrid retrieval, tuning | Not started |
| 0.8 | 14, 15 | Capture inbox and screening | Not started |
| 0.9 | 16, 17 | Conflicts and maintenance | Not started |
| 1.0 | 18 | Release | Not started |

---

## Sprint 10b — Evaluation harness and FTS5 baseline

### Version and sprint

- **Version:** 0.6 series (release happens after Sprint 11, per `SPRINT.md`)
- **Sprint:** 10b
- **Branch:** `sprint-10b`
- **Status:** Planned, not started
- **Depends on:** Sprint 10a (merged to `main`)

### Goal

Make retrieval quality measurable before anything in retrieval changes. By the end of this sprint, `amco eval run` reports recall@k, MRR, memory tokens and latency against a fixed fixture set, runs can be saved and compared, and an FTS5 baseline is committed so later sprints (embeddings, tuning, classifier) are judged against numbers instead of impressions.

Ship rule carried into later sprints: a measured change is judged by individual queries, with no more than 1 net query lost overall.

### Added

Planned scope, from `SPRINT.md` tasks S10-11 to S10-25 and S10-30, S10-31. Update this list to what actually shipped.

- New package `src/amco/evaluation/`:
  - `fixtures.py`: dataclasses for fixture memories, queries and the set; `load_fixtures()`; `fixture_hash()` (sha256 of canonical JSON); validation with clear errors (duplicate keys, empty content, unknown keys in `expect` or `supersedes`, bad types, negative `age_days`, bad `expires_in_days`, unknown fields).
  - `metrics.py`: pure functions `recall_at_k`, `reciprocal_rank`, `precision_at_k`, `percentile`, plus aggregation. Negative queries are excluded from recall and MRR and counted in a separate false-inclusion rate.
  - `runner.py`: `build_database()` (creates fixture memories, resolves `supersedes` keys, backdates timestamps from `age_days`, returns a key-to-ID map) and `run_suite()` (fresh Working Memory per query, calls `ame.prepare`, never calls `ame.finish`, so `use_count` stays untouched and runs are repeatable).
  - `store.py`: save and load runs as JSON with a safe name check (`[A-Za-z0-9._-]{1,64}`) and run metadata (AMCO version, Python, platform, SQLite version, FTS5 availability, fixture name and hash, k, mode, ranking weights, half-life, context settings).
  - `report.py`: Rich tables for a run and for a comparison (metric deltas, plus the queries that flipped between hit and miss).
- `src/amco/cli/evaluation.py`: `eval run [--fixtures PATH] [--k N] [--tag TAG] [--save NAME] [--out FILE] [--verbose] [--json] [--min-recall X] [--min-mrr X]`, `eval compare A B [--force]`, `eval list`. The `--min-*` options exit with code 1 below the threshold so CI and later sprints can gate on them.
- `src/amco/evaluation/fixtures/default.json`: about 30 memories and at least 40 queries, tagged `exact`, `stem`, `multi-term`, `paraphrase` (at least 8, expected to miss under FTS5), `followup`, `history`, `superseded`, `expired`, `duplicate`, `conflict`, `negative`, `chitchat`. Expiry is written as `expires_in_days` (relative), never as an absolute date.
- `config.eval_dir()` and the `AMCO_EVAL_DIR` setting (default `<database folder>/eval`).
- `benchmarks/fts-baseline-0.6.json`: the committed FTS5 baseline, with its headline numbers recorded in `DEV_PROGRESS.md`.
- CI smoke step: `amco eval run` after the non-editable install (FTS only, no Ollama).
- A short "How to extend the fixtures" note in `SPRINT.md`.

### Changed

- `ame.retrieve()` and `ame.prepare()` accept an optional `db_path`, passed down to `search_memories`, so the harness can target a temporary database without touching the environment. Default behavior is unchanged.
- `cli/__init__.py` registers the new group: `app.add_typer(eval_app, name="eval")`.
- `pyproject.toml`: `[tool.setuptools.package-data]` for `evaluation/fixtures/*.json`; fixtures load through `importlib.resources`, so they exist after a non-editable install.
- `tests/test_architecture.py`: `evaluation` added to `RANKS` (imports `ame`, `storage`, `working`, `config`, so it ranks above them).
- `tests/snapshots/cli_structure.json` regenerated on purpose for the new `eval` group, diff read before committing; `test_command_names_and_order_are_stable` updated from the regenerated snapshot.
- Public-surface contract tests extended with the evaluation names.
- Fixtures are frozen for 0.6 at the end of this sprint. They are not frozen permanently; later versions may change them with a recorded re-baseline.

### Fixed

- None so far. Anything found and fixed during the sprint goes here.

### Tests

Planned new files (all run without Ollama):

- `tests/test_eval_metrics.py`: recall, MRR and precision edge cases (empty expected, duplicates, k larger than results), percentile maths.
- `tests/test_eval_fixtures.py`: every validation error, the packaged fixtures load, every `expect` key exists, the hash is stable.
- `tests/test_eval_runner.py`: a tiny fixture end to end with exact expected numbers; superseded and expired memories never returned; `use_count` untouched after a run; the FTS-fallback path.
- `tests/test_eval_store.py`: save, load and compare; bad names rejected; mismatched fixture hash refused.
- `tests/test_cli_eval.py`: `eval run` with a tiny `--fixtures` file, `--save` and `compare`, `--min-recall` exit code.

Total after Sprint 10b: `<N>` tests (fill in at close-out; the Sprint 10a total is the starting point).

### Acceptance Criteria

Tick each box only after checking it.

- [ ] `amco eval run` prints recall@k, MRR, memory tokens and latency, overall and per tag, and can save the run.
- [ ] `amco eval compare` shows metric deltas and which queries flipped between hit and miss.
- [ ] `--min-recall` and `--min-mrr` exit with code 1 when a metric falls below the threshold.
- [ ] Fixtures validate with clear errors, use `expires_in_days`, and the default fixtures load after a non-editable install.
- [ ] A run never changes `use_count`, so repeating a run gives identical results.
- [ ] The FTS5 baseline is committed in `benchmarks/` and its headline numbers are recorded in `DEV_PROGRESS.md`.
- [ ] The schema fingerprint is unchanged; the CLI snapshot was regenerated deliberately and its diff reviewed.
- [ ] Tests pass without Ollama, and CI is green on Ubuntu and Windows with Python 3.11 and 3.13, including the eval smoke step.

Demo: `amco eval run --save baseline`, then `amco eval run --verbose`, and read the paraphrase misses.

Out of scope: embeddings, tuning, new memory columns.

### What's Next

Within this sprint, in order:

1. S10-11 to S10-14: fixture dataclasses, validation, `expires_in_days`, the default fixture file, and packaging.
2. S10-15 to S10-19: metrics, `db_path` plumbing, `build_database()`, `run_suite()`, aggregation.
3. S10-20 to S10-22: `eval_dir()`, run storage, reports.
4. S10-23 to S10-25: the `eval` CLI group, its registration, the CI smoke step.
5. S10-26 to S10-31: `RANKS`, snapshot and contract updates, the baseline run, and the fixtures how-to note.

Open items to settle before coding:

- Reports should show raw query counts (for example `37/40`) next to any percentage, since the ship rule counts individual queries.
- Fixture set size: the plan says at least 40 queries; decide whether to aim higher before the baseline is frozen.

After this sprint: Sprint 11 (real Long-Term Memory), starting with `amco eval run --save pre-sprint-11` as its regression reference. Queries not tagged `ltm` must show identical results afterwards.