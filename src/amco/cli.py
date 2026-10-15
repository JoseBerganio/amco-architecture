# SPDX-License-Identifier: GPL-2.0-or-later
#
# AMCO — Adaptive Memory Controller
# Copyright (C) 2026  Jose Berganio
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .config import model_name
from . import __version__
from .engine import answer, context_settings
from .storage import (
    VALID_TYPES,
    add_memory,
    database_path,
    delete_memory,
    get_memory,
    list_memories,
    rebuild_index,
    search_memories,
    session,
    update_memory,
)
from .working import WorkingMemory


app = typer.Typer(help="AMCO — Adaptive Memory Controller", no_args_is_help=True)
memory_app = typer.Typer(help="Manage stored memories.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")
console = Console()
err_console = Console(stderr=True)

TYPE_HELP = f"Memory type: {' or '.join(VALID_TYPES)}."
CONFIDENCE_HELP = "Confidence from 0 to 1 (1 = confirmed)."


@app.callback()
def main() -> None:
    """AMCO local-first memory orchestration prototype."""


@app.command()
def version() -> None:
    """Show AMCO version."""
    console.print(f"AMCO {__version__}")


@app.command()
def init() -> None:
    """Initialize the local workspace and SQLite database."""
    path = database_path()
    with session(path):
        pass
    console.print(f"[green]AMCO initialized.[/green] Database: {path}")


@memory_app.command("add")
def memory_add(
    content: str = typer.Argument(..., help="Text to save as a memory."),
    category: str = typer.Option("general", "--category", "-c", help="Memory category."),
    memory_type: str = typer.Option("persistent", "--type", "-t", help=TYPE_HELP),
    confidence: float = typer.Option(1.0, "--confidence", min=0.0, max=1.0, help=CONFIDENCE_HELP),
) -> None:
    """Add an explicitly approved memory."""
    try:
        memory_id = add_memory(content, category, memory_type, confidence=confidence)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Saved memory [bold]#{memory_id}[/bold].")


@memory_app.command("list")
def memory_list(
    memory_type: Optional[str] = typer.Option(None, "--type", "-t", help=TYPE_HELP),
) -> None:
    """List stored memories."""
    try:
        records = list_memories(memory_type=memory_type)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not records:
        console.print("No memories stored yet.")
        return
    table = Table("ID", "Type", "Category", "Conf", "Updated", "Content")
    for item in records:
        table.add_row(
            str(item["id"]),
            item["memory_type"],
            item["category"],
            f"{item['confidence']:.2f}",
            item["updated_at"] or item["created_at"],
            item["content"],
        )
    console.print(table)


@memory_app.command("inspect")
def memory_inspect(
    memory_id: int = typer.Argument(..., min=1, help="Memory ID."),
) -> None:
    """Show a memory's full content and metadata."""
    item = get_memory(memory_id)
    if item is None:
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)
    console.print(f"[bold]Memory #{item['id']}[/bold]")
    console.print(f"  Type:       {item['memory_type']}")
    console.print(f"  Category:   {item['category']}")
    console.print(f"  Source:     {item['source']}")
    console.print(f"  Confidence: {item['confidence']:.2f}")
    console.print(f"  Used:       {item['use_count']} times in prompts")
    console.print(f"  Created:    {item['created_at']}")
    console.print(f"  Updated:    {item['updated_at']}")
    console.print("  Content:")
    console.print(f"    {item['content']}", markup=False)


@memory_app.command("update")
def memory_update(
    memory_id: int = typer.Argument(..., min=1, help="Memory ID."),
    content: Optional[str] = typer.Option(None, "--content", help="New content."),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="New category."),
    memory_type: Optional[str] = typer.Option(None, "--type", "-t", help=TYPE_HELP),
    confidence: Optional[float] = typer.Option(
        None, "--confidence", min=0.0, max=1.0, help=CONFIDENCE_HELP
    ),
) -> None:
    """Update a memory's content, category, type, or confidence."""
    try:
        updated = update_memory(memory_id, content, category, memory_type, confidence=confidence)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not updated:
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)
    console.print(f"Updated memory [bold]#{memory_id}[/bold].")


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Words to search for."),
    limit: int = typer.Option(5, min=1, max=50, help="Maximum results."),
    explain: bool = typer.Option(False, "--explain", help="Show how each result was scored."),
) -> None:
    """Full-text search over memories, ranked by relevance, confidence, freshness and usefulness."""
    records = search_memories(query, limit=limit)
    if not records:
        console.print("No matching memories.")
        return
    for item in records:
        console.print(
            f"[bold]#{item['id']}[/bold] \\[{item['memory_type']}/{item['category']}] "
            f"{escape(item['content'])}",
            highlight=False,
        )
        if explain:
            p = item["score_parts"]
            console.print(
                f"    score={item['score']:.3f}  R={p['relevance']:.2f} "
                f"C={p['confidence']:.2f} F={p['freshness']:.2f} U={p['usefulness']:.2f}",
                markup=False,
                highlight=False,
            )


@memory_app.command("reindex")
def memory_reindex() -> None:
    """Rebuild the full-text search index from the stored memories."""
    if rebuild_index():
        console.print("Search index rebuilt.")
    else:
        err_console.print("Full-text search (FTS5) is not available in this SQLite build.")
        raise typer.Exit(code=1)


@memory_app.command("delete")
def memory_delete(
    memory_id: int = typer.Argument(..., min=1),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete a memory by ID."""
    if not yes:
        confirmed = typer.confirm(f"Delete memory #{memory_id}?", default=False)
        if not confirmed:
            console.print("Cancelled.")
            raise typer.Exit()
    if delete_memory(memory_id):
        console.print(f"Deleted memory #{memory_id}.")
    else:
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)


CHAT_HELP = """Chat commands:
  /task <text>      Set the current task (kept in Working Memory)
  /task             Show the current task
  /task clear       Clear the current task
  /remember <text>  Save text to Persistent Memory
  /status           Show Working Memory and context usage
  /clear            Reset Working Memory (history and task)
  /help             Show this help
  /exit             Quit"""


def _handle_chat_command(line: str, working: WorkingMemory) -> None:
    command, _, arg = line.partition(" ")
    command = command.casefold()
    arg = arg.strip()

    if command == "/help":
        console.print(CHAT_HELP, markup=False, highlight=False)
    elif command == "/task":
        if not arg:
            console.print(
                f"Current task: {working.task}" if working.task else "No task set.",
                markup=False,
            )
        elif arg.casefold() == "clear":
            working.set_task(None)
            console.print("Task cleared.")
        else:
            working.set_task(arg)
            console.print("Task set.")
    elif command == "/remember":
        if not arg:
            console.print("Usage: /remember <text>", markup=False)
        else:
            memory_id = add_memory(arg, category="chat", memory_type="persistent")
            console.print(f"Saved memory [bold]#{memory_id}[/bold] to Persistent Memory.")
    elif command == "/clear":
        working.clear()
        console.print("Working Memory cleared.")
    elif command == "/status":
        limit, reserved, _ = context_settings()
        console.print(
            f"Working Memory: {len(working.turns)} turns (~{working.tokens} tokens)"
        )
        console.print(f"Turns dropped to fit context: {working.dropped_turns}")
        console.print(
            f"Last prompt: ~{working.last_prompt_tokens} of {limit - reserved} usable tokens"
        )
        console.print(f"Task: {working.task or '(none)'}", markup=False)
    else:
        console.print("Unknown command. Type /help.")


def _describe_retrieved(memories: list[dict]) -> str:
    parts = []
    for m in memories:
        label = f"#{m['id']}"
        if "score" in m:
            label += f" ({m['score']:.2f})"
        parts.append(label)
    return ", ".join(parts)


@app.command()
def chat() -> None:
    """Start a memory-enabled interactive chat with Ollama."""
    working = WorkingMemory()
    console.print("AMCO chat — type /help for commands, /exit to quit.")
    console.print(f"Model: {model_name()}")
    while True:
        try:
            query = console.input("\n[bold cyan]You[/bold cyan]> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            break
        if query.casefold() in {"/exit", "/quit"}:
            console.print("Goodbye.")
            break
        if not query:
            continue
        if query.startswith("/"):
            _handle_chat_command(query, working)
            continue
        try:
            response, used_memories = answer(query, working)
        except RuntimeError as exc:
            console.print(f"[red]Model error:[/red] {exc}")
            continue
        console.print("\n[bold green]AMCO[/bold green]> ", end="")
        console.print(response, markup=False, highlight=False)
        if used_memories:
            console.print(
                f"[dim]Retrieved memories: {_describe_retrieved(used_memories)}[/dim]"
            )
        else:
            console.print("[dim]Retrieved memories: none[/dim]")