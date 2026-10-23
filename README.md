# AMCO — Adaptive Memory Controller

A local-first memory layer for local LLMs. AMCO stores information outside the model, retrieves only what is relevant to the current question, and fits it into the model's context window.

**Status:** early prototype (v0.5.0). The CLI, SQLite storage with full-text search and ranking, Working Memory, the Adaptive Memory Engine pipeline, memory hygiene (duplicates, supersession, expiry), lifecycle review, and Ollama integration work. Version 0.5 reorganized the code into packages and added a model adapter interface, with no change to the commands or the database. Semantic search and automatic memory management are still to come.

## Why AMCO

Local models have a limited context window and forget everything between sessions. AMCO sits between you and the model and decides what the model should see for the task at hand, rather than giving it everything it has ever stored. It does not retrain or modify the model.

## Features

- **Persistent memory in SQLite**: add, list, inspect, update, search, supersede, and delete memories, with category, type (`persistent` or `long_term`), confidence, source, expiry, and timestamps.
- **Full-text search with ranking**: SQLite FTS5 finds memories by word (with stemming), then ranks them by relevance, confidence, freshness, and usefulness. Use `--explain` to see how each result was scored.
- **Adaptive Memory Engine (AME)**: every chat message goes through a pipeline that classifies the request, decides how much to retrieve, drops duplicates, flags overlapping memories, fits everything into the context budget, and builds the prompt. Greetings skip retrieval, and short follow-ups use your recent messages and pinned task. Type `/why` to see how the last answer's context was chosen.
- **Working Memory in chat**: conversation history, a pinned task, and a token-budgeted prompt that drops the oldest turns first when the context fills up.
- **Context budgeting**: retrieved memories are selected to fit a token budget, and a memory is skipped rather than cut short.
- **Memory hygiene**: identical memories are blocked, similar ones are flagged, outdated memories can be superseded (hidden but kept and restorable), and memories can expire.
- **Lifecycle review**: `amco memory review` suggests deleting expired or long-superseded memories, archiving idle ones, and promoting well-used ones. Nothing changes unless you pass `--apply`.
- **Local model through an adapter**: talks to Ollama by default (Qwen 2.5 3B, 4-bit quantized). The engine depends on a small `ChatModel` interface rather than on Ollama itself, so other runtimes can be added without touching the memory logic.
- **Memories are treated as data, not instructions**: the system prompt tells the model not to follow instructions found inside retrieved memories.
- **User control**: memories are saved only when you explicitly add them, and you can inspect, edit, supersede, and delete any of them.
- **Tests run without Ollama**: the model is mocked in the test suite.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com) installed and running
- A pulled model (the default is `qwen2.5:3b`)

## Install

```bash
git clone https://github.com/JoseBerganio/amco-architecture.git
cd amco-architecture
python -m venv .venv
```

Activate the virtual environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Then install and set up:

```bash
python -m pip install -e ".[dev]"
ollama pull qwen2.5:3b
amco init
```

### Upgrading from 0.2.x

No action needed. Version 0.5 does not change the database, the commands, or their output.

```bash
cp ~/.amco/amco.sqlite3 ~/.amco/amco.sqlite3.bak                      # macOS/Linux
Copy-Item $HOME\.amco\amco.sqlite3 $HOME\.amco\amco.sqlite3.bak       # Windows PowerShell
```

## Quick start

```bash
amco memory add "My Project uses Python and SQLite for its prototype." --type persistent
amco memory list
amco memory search "storage" --explain
amco chat
```

Then ask something in the chat, such as `What does AMCO use for storage?`. After each answer, AMCO shows which memory IDs it retrieved.

## CLI reference

| Command | Purpose |
|---------|---------|
| `amco version` | Show the version |
| `amco init` | Create the workspace and database |
| `amco chat` | Interactive chat with memory retrieval |
| `amco memory add "text" [-c category] [-t type] [--confidence 0-1] [--expires DATE] [--supersedes ID] [--force]` | Save a memory (blocks exact duplicates unless `--force`) |
| `amco memory list [-t type] [--all]` | List active memories (`--all` includes superseded and expired) |
| `amco memory inspect <id>` | Show one memory in full |
| `amco memory update <id> [--content ...] [-c ...] [-t ...] [--confidence ...] [--expires DATE\|none]` | Edit a memory |
| `amco memory supersede <old-id> <new-id>` | Replace a memory with another (the old one is hidden, not deleted) |
| `amco memory restore <id>` | Bring a superseded memory back |
| `amco memory review [--apply] [--yes]` | Suggest (or apply) lifecycle changes |
| `amco memory search "words" [--limit N] [--explain]` | Ranked full-text search |
| `amco memory reindex` | Rebuild the search index |
| `amco memory delete <id> [--yes]` | Delete a memory |

### Chat commands

| Command | Purpose |
|---------|---------|
| `/task <text>` | Set the current task (kept in Working Memory) |
| `/task` | Show the current task |
| `/task clear` | Clear the current task |
| `/remember <text>` | Save text to Persistent Memory |
| `/status` | Show Working Memory and context usage |
| `/why` | Explain how the last answer's memories were chosen |
| `/clear` | Reset Working Memory (history and task) |
| `/help` | List chat commands |
| `/exit` | Quit |

## Configuration

Settings come from environment variables.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AMCO_DB_PATH` | `~/.amco/amco.sqlite3` | Database location |
| `AMCO_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `AMCO_MODEL` | `qwen2.5:3b` | Model name |
| `AMCO_PROVIDER` | `ollama` | Model adapter to use (only `ollama` exists so far) |
| `AMCO_CONTEXT_TOKENS` | `4096` | Context window, also sent to Ollama as `num_ctx` |
| `AMCO_RESERVED_OUTPUT_TOKENS` | `512` | Space kept free for the model's reply |
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

Ranking weights are starting defaults and have not been tuned yet.

Example (PowerShell):

```powershell
$env:AMCO_CONTEXT_TOKENS="2048"; amco chat
```

Set `AMCO_CONTEXT_TOKENS` to a value your machine can handle. A larger context window uses more RAM and slows responses.

## Testing

```bash
pytest
```

The tests use temporary databases and a mocked model, so Ollama does not need to be running.

GitHub Actions runs the suite on Ubuntu and Windows with Python 3.11 and 3.13. Contract tests guard the command tree, the database schema, and the public imports.

```
src/amco/
├── ame.py         # Adaptive Memory Engine: analysis, conflicts, budgeting, assembly
├── config.py      # All environment-based settings
├── engine.py      # Public answer() entry point (AME plus the model call)
├── lifecycle.py   # Memory review: expiry, supersession, archive, promote
├── ranking.py     # Scoring formula
├── working.py     # Working Memory and token estimation
├── cli/           # Typer commands: system, memory group, chat loop
├── models/        # Model adapter interface and the Ollama adapter
└── storage/       # SQLite: connection and FTS5 setup, records, hygiene, search
tests/             # pytest suite, including contract tests and snapshots
.github/workflows/ci.yml   # CI on Ubuntu and Windows, Python 3.11 and 3.13
```

## Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| 1 | Project foundation and CLI | Done |
| 2 | SQLite storage and memory commands | Done |
| 3 | Working Memory, context budgeting, local model | Done |
| 4 | Full-text search and ranking | Done (0.2) |
| 5 | Adaptive Memory Engine, memory hygiene, lifecycle review | Done (0.2) |
| 6 to 9 | Modularization: CLI, storage and model-adapter packages, central config, CI | Done (0.5) |
| Next | Automatic memory capture, smarter retrieval, TOML config, `stats`/`models`/`config` commands | Planned |

See [DEV_PROGRESS.md](DEV_PROGRESS.md) for the development log and what comes next.

## Known limitations

- Search matches words and their stems, not meaning; semantic search is not implemented yet.
- Overlapping memories are flagged to the model using a term-overlap heuristic, which cannot tell a contradiction from a complementary fact.
- The request classifier is rule-based and English-only.
- Short follow-up questions borrow terms from your recent messages and pinned task, but not from the model's replies.
- Ranking weights are untuned defaults.
- Token counts are estimates (about 4 characters per token).
- Older chat turns are dropped, not summarized.
- Memories are never saved automatically; use `amco memory add` or `/remember`.
- A 3B model may sometimes ignore or misuse retrieved memories. Use `/why` and the retrieved IDs shown after each answer to tell retrieval problems from model problems.
- Only the Ollama adapter is implemented so far; the adapter interface is in place for others.

## Privacy

Everything runs locally: the database lives on your machine (by default in `~/.amco/`), and the model runs through your local Ollama server. Local does not automatically mean private, though. Check where your logs, backups, and any synced folders end up.


## License

AMCO — Adaptive Memory Controller
Copyright (C) 2026  Jose Berganio

AMCO is free software; you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version (GPL-2.0-or-later).

AMCO is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details. The full license text is in [LICENSE](LICENSE).