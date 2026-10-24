# AMCO 0.5.0 — Modularization Update

Planning and tracking document for the 0.5.0 release.
Last updated: 2026-10-18 · Status: planned · Baseline: `v0.2.0` (105 tests)

---

## 1. Purpose and scope

**Objective:** restructure AMCO's internals so the code is easier to maintain, test, and extend, with no change to what users see or what the database contains.

**In scope**
- Split `cli.py` into a `src/amco/cli/` package.
- Split `storage.py` into a `src/amco/storage/` package.
- Add a model adapter contract (`src/amco/models/`) and decouple the engine from Ollama specifics.
- Centralize configuration: environment reads move into `config.py`. No TOML.
- Review dependencies between all modules and enforce the direction with a test.
- Add the safety nets that make the refactor verifiable: contract tests, a CI workflow, and packaging checks.

**Out of scope (deferred to 0.6.0 or later)**
- Automatic memory capture, smarter retrieval, maintenance improvements, coding-session support.
- TOML configuration, embeddings or semantic search, and the `stats`, `models`, and `config` commands.
- Any schema change, SQL change, new runtime dependency, or new, renamed, or removed CLI command or option.
- Any change to user-visible output text or error messages.

**Deliverable:** a working AMCO with identical user-facing behavior and a clearer internal structure.

---

## 2. Ground rules

1. **Move before change.** Code is moved verbatim first. Tidying happens in a separate commit, never in the same one as a move.
2. **One module per commit**, with `pytest` run after each.
3. **No edits to existing tests in Sprints 6 to 8.** New test files are allowed. Sprint 9 is the only sprint allowed to edit existing tests, and only import and patch paths, never assertions.
4. **No behavior drift.** No new SQL, no schema change, no new runtime dependencies, no changed messages.
5. **Settings are read at call time, never at import time.** Tests set environment variables per test, so caching a setting in a module-level constant would break them.
6. **Preserve import surfaces** with re-exports until Sprint 9 (see section 5).
7. **Essential abstractions only.** One adapter contract and one provider factory. No repository classes or abstract storage interfaces, because nothing needs a second implementation yet.
8. **Documentation only on request.** DEV_PROGRESS.md receives summaries only. Detailed records live in the local sprint documents.

---

## 3. Starting point (v0.2.0)

**Modules:** `__init__`, `ame`, `cli`, `config`, `engine`, `lifecycle`, `model`, `ranking`, `storage`, `working`.
**Tests:** 105 across 12 files. None need Ollama.
**Entry point:** `amco = "amco.cli:app"`. Packaging uses `setuptools` with `packages.find` under `src`.

**Current dependency direction**
`config → ranking → storage → ame / lifecycle → engine → cli`, with `model → config` and `engine → model`.

**Known coupling that shapes this plan**
- `storage.py` holds six concerns: connection and migration, FTS setup, CRUD, supersession, duplicate checks, and retrieval. `add_memory(supersedes=)` and `delete_memory` both touch supersession logic, so CRUD and supersession are entangled.
- `cli.py` holds the app assembly, helpers, memory commands, and the whole chat loop.
- `engine.ollama_chat` is the seam many tests patch, and `engine` re-exports `context_settings` for `cli`.
- `ranking.weights_from_env` and `storage.database_path` read environment variables outside `config.py`.
- Several tests patch internals by module path (section 5).

---

## 4. Target architecture

```
src/amco/
├── __init__.py          # __version__
├── config.py            # all settings and environment reads (call-time)
├── ranking.py           # unchanged logic; env names move to config
├── working.py           # unchanged
├── ame.py               # unchanged logic
├── lifecycle.py         # unchanged logic
├── engine.py            # answer(); depends on models, not on Ollama
├── model.py             # TEMPORARY shim (removed in Sprint 9)
├── models/
│   ├── __init__.py      # get_model() factory
│   ├── base.py          # ChatModel contract, ModelError
│   └── ollama.py        # OllamaChat (logic moved verbatim)
├── storage/
│   ├── __init__.py      # public API re-exports
│   ├── text.py          # pure text helpers: STOPWORDS, extract_terms, normalize_content, term_similarity
│   ├── db.py            # database_path, connect, migrate, FTS setup, session, rebuild_index
│   ├── memories.py      # validators, add/list/get/update/delete, status, record_usage
│   ├── hygiene.py       # supersede, restore, check_duplicates
│   └── search.py        # search_candidates, search_memories, keyword fallback
└── cli/
    ├── __init__.py      # builds `app`, registers everything
    ├── common.py        # consoles, shared help strings, status label
    ├── system.py        # version, init
    ├── memory.py        # the `memory` command group
    └── chat.py          # chat help text, command handler, chat loop
```

**Allowed dependency direction** (a module may import only from modules to its left)

```
config ← ranking, working, models ← storage.text ← storage.db ← storage.memories
       ← storage.hygiene ← storage.search ← ame, lifecycle ← engine ← cli
```

Inside `storage`: `text` (no dependencies) → `db` → `memories` → `hygiene` → `search`. `search` also uses `ranking`. No cycles are allowed, and a test will enforce this (Sprint 8, extended in Sprint 9).

**Adapter contract (essential only)**
- `ChatModel`: a `name` and `chat(messages: list[dict[str, str]]) -> str`.
- `ModelError(RuntimeError)`: adapters raise this. Because it subclasses `RuntimeError`, existing `except RuntimeError` handlers and tests keep working.
- `get_model()`: returns the configured adapter. One new setting, `AMCO_PROVIDER`, default `ollama`. An unknown value gives a clear error. Default behavior is identical to today.
- `answer(query, working=None, model=None)`: the optional `model` parameter lets tests inject a fake adapter.

---

## 5. Compatibility contract

Everything below must remain importable and behave identically through Sprint 8.

**Import surfaces to preserve**

| Module | Names that must stay importable |
|---|---|
| `amco.storage` | `DEFAULT_DB`, `VALID_TYPES`, `DEFAULT_CONFIDENCE`, `MAX_QUERY_TERMS`, `SIMILARITY_THRESHOLD`, `STOPWORDS`, `database_path`, `connect`, `session`, `memory_status`, `add_memory`, `list_memories`, `get_memory`, `update_memory`, `delete_memory`, `supersede_memory`, `restore_memory`, `normalize_content`, `term_similarity`, `check_duplicates`, `extract_terms`, `search_candidates`, `search_memories`, `record_usage`, `rebuild_index`, and the private `_has_fts` (a test patches it) |
| `amco.engine` | `answer`, `select_memories`, `retrieval_query`, `ollama_chat`, `context_settings`, `SYSTEM_PROMPT`, `format_memory` |
| `amco.model` | `ollama_chat`, `httpx` (a test patches `model.httpx.post`) |
| `amco.cli` | `app`, `answer` (a test patches `amco.cli.answer`) |
| `amco.ame`, `amco.ranking`, `amco.working`, `amco.lifecycle`, `amco.config` | unchanged, including `ranking.weights_from_env` |

**Test seams that a naive refactor would break**

| Test file | What it patches | Sprint that threatens it | Temporary seam (Sprints 6 to 8) | Final form (Sprint 9) |
|---|---|---|---|---|
| `test_cli.py` | `amco.cli.answer` | 6 | A thin `chat` command in `cli/__init__.py` resolves `answer` from the `amco.cli` namespace at call time and passes it into the chat loop in `cli/chat.py`. | Keep, or re-point to `amco.cli.chat`. |
| `test_search.py` | `amco.storage._has_fts` | 8 | `search.py` looks up `_has_fts` through the `amco.storage` package at call time. | Patch `amco.storage.db._has_fts`, with `search.py` calling `db._has_fts`. |
| `test_engine.py`, `test_engine_context.py`, `test_engine_retrieval.py`, `test_ame.py` | `engine.ollama_chat` | 7 | `engine.ollama_chat` stays as a function that delegates to the configured adapter, and `answer()` still calls it. | Inject a fake `ChatModel` with `answer(..., model=fake)`. |
| `test_model.py` | `model.httpx.post`, calls `model.ollama_chat` | 7 | `amco/model.py` stays as a shim exposing `httpx` and `ollama_chat`. | Point at `amco.models.ollama`. |

**Database compatibility:** the schema, triggers, FTS table, and every SQL statement stay unchanged. A 0.2.0 database and a 0.5.0 database are interchangeable.

---

## 6. Sprint plan overview

| Sprint | Branch | Focus | Size | Risk |
|---|---|---|---|---|
| 6 | `sprint-6-cli-split` | Safety net, CI, CLI split | Medium | Low |
| 7 | `sprint-7-adapter-config` | Model adapter contract, config centralization | Medium | Medium |
| 8 | `sprint-8-storage-split` | Storage package split, layering test | Large | High |
| 9 | `sprint-9-cleanup-release` | Shim removal, test path migration, final review, release | Small–Medium | Medium |

If Sprint 8 goes smoothly, Sprint 9's cleanup may fold into it (decision at the Sprint 8 review). Sprints 6 to 8 change no existing test.

---

## 7. Sprint details

### Sprint 6 — Safety net, CI, and CLI split

**Goal:** make the refactor verifiable, then split the CLI, which nothing else depends on.

**Tasks**
1. **Baseline.** Confirm the `v0.2.0` tag exists and record the `pytest` count (expected 105).
2. **Contract tests (new files only), written and passing against v0.2.0 code before anything moves:**
   - *CLI structure snapshot:* walk the Typer command tree (via `typer.main.get_command(app)`) and compare command names, their order, and each option's name, short flag, default, required flag, and help text. This is structural, not rendered help text, so it is not affected by terminal width or Rich versions.
   - *Import-surface test:* assert every name in section 5 is importable from its module.
   - *Schema fingerprint:* a database created with the exact v0.2.0 schema opens correctly, and its tables, columns, triggers, and FTS table match the v0.2.0 set after migration.
3. **CI workflow** (GitHub Actions): run on pull requests and pushes to the sprint branches, on Ubuntu and Windows with Python 3.11 and 3.13. Steps: install with `pip install -e ".[dev]"`, run `pytest`, then a non-editable install plus `amco --help`.
4. **`.gitignore`:** add `build/` and `dist/` (a non-editable install can leave a `build/` folder in the repo).
5. **CLI split**, moving code verbatim:
   - `cli/common.py`: `console`, `err_console`, `TYPE_HELP`, `CONFIDENCE_HELP`, `_status_label`.
   - `cli/system.py`: `version`, `init`.
   - `cli/memory.py`: the `memory` command group and every subcommand.
   - `cli/chat.py`: `CHAT_HELP`, the chat command handler, `_describe_retrieved`, and the chat loop taking the answer function as an argument.
   - `cli/__init__.py`: builds `app`, keeps the original registration order and docstrings, registers the groups and commands, and provides the thin `chat` command that preserves the `amco.cli.answer` seam.
6. Delete `cli.py` and clear stale `__pycache__` folders.

**Acceptance criteria**
- All 105 existing tests pass with zero edits, plus the new contract tests.
- The CLI structure snapshot matches the v0.2.0 snapshot exactly.
- `amco = "amco.cli:app"` still works unchanged.
- CI is green on both operating systems and both Python versions.
- Every new folder has an `__init__.py`, and a non-editable install works.

**Risks:** the `amco.cli.answer` seam, a missing `__init__.py`, and a stale `cli.py` or `__pycache__` shadowing the new package.

---

### Sprint 7 — Model adapter contract and config centralization

**Goal:** the engine depends on a contract, not on Ollama, and settings live in one place.

**Tasks**
1. `models/base.py`: `ChatModel` and `ModelError(RuntimeError)`.
2. `models/ollama.py`: `OllamaChat`, with the HTTP and error-handling logic moved verbatim. Error messages stay identical (a test checks the `ollama pull <model>` hint).
3. `models/__init__.py`: `get_model()` and the `AMCO_PROVIDER` setting (default `ollama`).
4. **Shims:** `amco/model.py` keeps `ollama_chat` and exposes `httpx`. `engine.ollama_chat` delegates to the adapter and is still the function `answer()` calls.
5. `answer(query, working=None, model=None)`: optional injection, default behavior unchanged.
6. **Config centralization:** move the `AMCO_DB_PATH` read and `DEFAULT_DB` into `config.py` (storage re-exports both), move the ranking-weight environment names into `config.py` (with `ranking.weights_from_env` kept as a wrapper), and add the provider setting. Every read stays at call time.
7. **New tests:** the adapter honors model, URL, context, and timeout settings; `ModelError` is a `RuntimeError`; an unknown provider gives a clear error; `answer(model=fake)` works; the import-surface test is extended to `amco.models`.

**Acceptance criteria**
- All earlier tests pass untouched.
- Error messages and request payloads are byte-identical to 0.2.0.
- Nothing in `engine.py` or `ame.py` imports Ollama or `httpx`.
- The CLI structure snapshot is unchanged, because the only new setting is an environment variable.

**Risks:** a setting cached at import time, drifted error messages, and an unnecessary abstraction growing beyond the one contract.

---

### Sprint 8 — Storage split

**Goal:** split the most depended-on module without changing behavior.

**Tasks**
1. **Dependency review first.** Write down the import graph and confirm the order `text → db → memories → hygiene → search`.
2. **Move in this order,** one module per commit with `pytest` after each, re-exporting from `storage/__init__.py` so imports keep working at every step:
   1. `text.py` (pure functions, no database)
   2. `db.py` (including `rebuild_index`)
   3. `memories.py`
   4. `hygiene.py`
   5. `search.py`
3. `storage/__init__.py` re-exports the full surface in section 5, including `_has_fts`.
4. Implement the `_has_fts` seam as described in section 5.
5. Delete `storage.py` and clear stale `__pycache__` folders.
6. **Architecture test (new):** scan imports and assert the allowed direction in section 4, so a cycle fails the build.
7. **Review the diff of every move** with `git diff --color-moved` to confirm code was moved, not rewritten.

**Acceptance criteria**
- All earlier tests pass untouched, and the schema fingerprint test is unchanged.
- No operation opens more connections or runs more queries than in 0.2.0.
- `ame.py` and `lifecycle.py` import only from the public `amco.storage` surface.
- The architecture test passes, and CI is green.
- A non-editable install works.

**Risks:** import cycles, the `_has_fts` seam, a moved line silently edited, and a validator or constant left behind in the wrong module.

---

### Sprint 9 — Cleanup, shim removal, and release

**Goal:** remove the temporary scaffolding and ship 0.5.0.

**Tasks**
1. **Migrate test patch paths only** (assertions untouched), according to the "Final form" column in section 5.
2. **Remove the shims:** `amco/model.py`, `engine.ollama_chat`, the temporary `_has_fts` seam, and re-exports that are no longer needed. The Python API is not documented and AMCO is pre-1.0, so this is acceptable, but note it in the release notes.
3. Extend the architecture test to cover the whole package.
4. Final dependency and naming review across all modules.
5. **Full regression:** `pytest` on the CI matrix, the manual smoke run on a copy of your real 0.2.0 database, and a non-editable install check.
6. **Release 0.5.0:** bump the version, update README (project layout) and a short DEV_PROGRESS.md summary on request, tag `v0.5.0`, and create the GitHub release.

**Acceptance criteria**
- The only test edits are import and patch paths, and the diff shows no assertion changed.
- The shims are gone and every test still passes.
- Section 12 (release checklist) is complete.

---

## 8. Quality gates (every sprint)

A sprint merges only if all of these hold:

1. `pytest` passes with at least the baseline count plus new tests, and no existing assertion was edited (Sprints 6 to 8).
2. The CLI structure snapshot, import-surface test, and schema fingerprint test pass.
3. CI is green on both operating systems and both Python versions.
4. **Fresh install check**, from outside the repo:
```bash
   python -m venv ../amco-check
   ../amco-check/bin/pip install .            # Windows: ..\amco-check\Scripts\pip install .
   ../amco-check/bin/amco --help              # Windows: ..\amco-check\Scripts\amco --help
```
5. **Manual smoke run** (back up the database first): `add → list → search --explain → supersede → restore → review`, then `amco chat` with Ollama running, a question, `/why`, `/remember`, and `/exit`.
6. No version bump and no tag until the 0.5.0 release.

**Cleanup commands after deleting a module that became a package**

```bash
find . -name __pycache__ -type d -prune -exec rm -rf {} +                      # macOS/Linux
Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force   # PowerShell
```

If imports fail after adding packages, re-run `pip install -e ".[dev]"`.

---

## 9. Git and review workflow

- One branch per sprint, created from an up-to-date `main`. Nothing goes straight to `main`.
- Small commits with clear messages (`Move X to Y, no logic change`, then `Tidy Y`).
- Push the branch, open a pull request, wait for CI to be green, and merge using a **merge commit (not squash)**, so the move-then-tidy history stays reviewable and individual commits can be reverted.
- Optionally require the CI check before merging (GitHub branch protection). The workflow must have run once before it appears in the list.
- Pull request checklist: gates 1 to 6 above, "no existing test edited" (Sprints 6 to 8), "no SQL or schema change", and "no output text changed".

```bash
git checkout main && git pull
git checkout -b sprint-6-cli-split
# work, commit, run pytest
git push -u origin sprint-6-cli-split
# open PR, wait for green, merge, then:
git checkout main && git pull && git branch -d sprint-6-cli-split
```

---

## 10. Risk register

| Risk | Sprint | Mitigation |
|---|---|---|
| A test patch no longer reaches the moved code | 6, 7, 8 | Temporary seams (section 5), tests untouched until Sprint 9 |
| A new package folder lacks `__init__.py`, so a built wheel omits it | 6, 7, 8 | Fresh non-editable install check in every sprint, run in CI |
| A stale module or `__pycache__` shadows the new package | 6, 8 | Delete the old file and clear caches in the same commit |
| Import cycles after the storage split | 8 | Dependency review first, architecture test |
| Silent behavior change while tidying | all | Move first, tidy second, `--color-moved` review |
| A setting cached at import time | 7 | Ground rule 5, tests that set environment variables after import |
| Schema or SQL drift | 6 to 9 | Schema fingerprint test, no SQL edits |
| Scope creep from the capability backlog | all | Out-of-scope list, deferred to 0.6.0 |
| Output text changes break user expectations | all | CLI structure snapshot and unchanged messages |

---

## 11. Rollback

- `v0.2.0` is the permanent rollback point, and the schema never changes, so the same database works with either version.
- A bad sprint is reverted by reverting its merge commit on GitHub, which restores `main` to the previous green state.
- Always copy `~/.amco/amco.sqlite3` before manual smoke runs.

---

## 12. Release checklist for 0.5.0

- [ ] All four sprints (or three, if folded) merged and green
- [ ] `pytest` passes on the CI matrix (Ubuntu and Windows, Python 3.11 and 3.13)
- [ ] CLI structure snapshot unchanged from v0.2.0
- [ ] Schema fingerprint unchanged from v0.2.0
- [ ] Manual smoke run done on a copy of a real database
- [ ] Non-editable install works on both operating systems
- [ ] `__version__` and `pyproject.toml` set to `0.5.0`
- [ ] README (project layout) and DEV_PROGRESS.md summary updated (on request)
- [ ] Release notes mention removed internal modules (`amco.model`, `engine.ollama_chat`)
- [ ] Tag `v0.5.0` pushed and GitHub release created

---

## 13. Next version (0.6.0 candidates, not part of this release)

- Automatic memory capture: proposals only, stored separately, approved by the user, screened for secrets, checked against the duplicate and conflict logic.
- Memory maintenance improvements (near-duplicates in `review`, richer conflict handling).
- Smarter retrieval, preceded by a small benchmark so the improvement can be measured.
- Coding-session support, after deciding project scoping and how code counts against the token budget.
- TOML configuration, and the `stats`, `models`, and `config` commands.

---

## 14. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| D1 | Add the `AMCO_PROVIDER` setting with only `ollama` registered | Yes. It is the minimum needed for a provider factory. |
| D2 | CI matrix and required status check | Ubuntu + Windows, Python 3.11 + 3.13, check required before merge |
| D3 | Remove `amco.model` and `engine.ollama_chat` in Sprint 9 | Yes. Internal modules, pre-1.0, noted in the release notes. |
| D4 | Merge method | Merge commit, not squash |
| D5 | Three or four sprints | Decide at the Sprint 8 review |

---

## 15. Sprint log

| Sprint | Branch | Status | PR | Notes |
|---|---|---|---|---|
| 6 | `sprint-6-cli-split` | Planned | | |
| 7 | `sprint-7-adapter-config` | Planned | | |
| 8 | `sprint-8-storage-split` | Planned | | |
| 9 | `sprint-9-cleanup-release` | Planned | | |

Per-sprint detail (Added, Changed, Tests, Acceptance criteria, Notes) is appended here as each sprint closes.