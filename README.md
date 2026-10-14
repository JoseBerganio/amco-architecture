# AMCO — Adaptive Memory Controller

A local-first memory layer for local LLMs. AMCO stores information outside the model, retrieves only what is relevant to the current question, and fits it into the model's context window.

> **Status:** early prototype (v0.1.0). The CLI, SQLite storage, keyword retrieval, Working Memory, and Ollama integration work. Ranking, semantic search, and automatic memory management are still to come.

## Why AMCO

Local models have a limited context window and forget everything between sessions. AMCO sits between you and the model and decides what the model should see for the task at hand, rather than giving it everything it has ever stored. It does not retrain or modify the model.

## Features

- **Persistent memory in SQLite**: add, list, inspect, update, search, and delete memories, with category, type (`persistent` or `long_term`), source, and timestamps.
- **Working Memory in chat**: conversation history, a pinned task, and a token-budgeted prompt that drops the oldest turns first when the context fills up.
- **Context budgeting**: retrieved memories are selected to fit a token budget, and a memory is skipped rather than cut short.
- **Local model through Ollama**: defaults to Qwen 2.5 3B (4-bit quantized).
- **Memories are treated as data, not instructions**: the system prompt tells the model not to follow instructions found inside retrieved memories.
- **User control**: memories are saved only when you explicitly add them, and you can inspect, edit, and delete any of them.
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

## Quick start

```bash
amco memory add "AMCO uses Python and SQLite for its prototype." --type persistent
amco memory list
amco chat
```

Then ask something in the chat, such as `What does AMCO use for storage?`. After each answer, AMCO shows which memory IDs it retrieved.

## CLI reference

| Command | Purpose |
|---------|---------|
| `amco version` | Show the version |
| `amco init` | Create the workspace and database |
| `amco chat` | Interactive chat with memory retrieval |
| `amco memory add "text" [-c category] [-t type]` | Save a memory |
| `amco memory list [-t type]` | List memories |
| `amco memory inspect <id>` | Show one memory in full |
| `amco memory update <id> [--content ...] [-c ...] [-t ...]` | Edit a memory |
| `amco memory search "words" [--limit N]` | Keyword search |
| `amco memory delete <id> [--yes]` | Delete a memory |

### Chat commands

| Command | Purpose |
|---------|---------|
| `/task <text>` | Set the current task (kept in Working Memory) |
| `/task` | Show the current task |
| `/task clear` | Clear the current task |
| `/remember <text>` | Save text to Persistent Memory |
| `/status` | Show Working Memory and context usage |
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
| `AMCO_CONTEXT_TOKENS` | `4096` | Context window, also sent to Ollama as `num_ctx` |
| `AMCO_RESERVED_OUTPUT_TOKENS` | `512` | Space kept free for the model's reply |
| `AMCO_MEMORY_TOKENS` | `1024` | Cap on tokens spent on retrieved memories |
| `AMCO_TIMEOUT_SECONDS` | `300` | Model request timeout |

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

## Project layout

```
src/amco/
├── cli.py        # Typer commands and chat loop
├── config.py     # Environment-based settings
├── engine.py     # Retrieval, memory selection, prompt assembly
├── model.py      # Ollama adapter
├── storage.py    # SQLite storage, migration, session helper
└── working.py    # Working Memory and token estimation
tests/            # pytest suite
```

## Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| 1 | Project foundation and CLI | Done |
| 2 | SQLite storage and memory commands | Done |
| 3 | Working Memory, context budgeting, local model | Done |
| 4 | Full-text search and ranking | Planned (0.2) |

Later work includes the three-tier memory lifecycle (working, persistent, long-term), semantic retrieval, conflict handling, diagnostics, and a model adapter interface. See [DEV_PROGRESS.md](DEV_PROGRESS.md) for the detailed log.

## Known limitations

- Retrieval is keyword-based and only looks at your latest message.
- Token counts are estimates (about 4 characters per token).
- Older chat turns are dropped, not summarized.
- Memories are never saved automatically; use `amco memory add` or `/remember`.
- A 3B model may sometimes ignore or misuse retrieved memories. Check the retrieved IDs shown after each answer to tell retrieval problems from model problems.

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