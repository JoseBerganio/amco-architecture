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

from typing import Callable

from ..config import context_settings, model_name
from ..storage import SchemaError, add_memory, check_duplicates
from ..working import WorkingMemory
from .common import console

CHAT_HELP = """Chat commands:
  /task <text>      Set the current task (kept in Working Memory)
  /task             Show the current task
  /task clear       Clear the current task
  /remember <text>  Save text to Persistent Memory
  /why              Explain how the last answer's memories were chosen
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
            exact, similar = check_duplicates(arg)
            if exact:
                console.print(f"Already remembered as [bold]#{exact['id']}[/bold].")
            else:
                memory_id = add_memory(arg, category="chat", memory_type="persistent")
                console.print(f"Saved memory [bold]#{memory_id}[/bold] to Persistent Memory.")
                if similar:
                    ids = ", ".join(f"#{m['id']}" for m in similar)
                    console.print(
                        f"Similar memories exist: {ids}. If this replaces one, run: "
                        f"amco memory supersede <old-id> {memory_id}",
                        markup=False,
                    )
    elif command == "/why":
        report = working.last_report
        if report is None:
            console.print("Nothing to explain yet. Ask a question first.")
        else:
            for text in report.lines():
                console.print(text, markup=False, highlight=False)
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


def _report_database_error(exc: SchemaError) -> None:
    console.print("[red]Database error:[/red]", end=" ")
    console.print(str(exc), markup=False, highlight=False)


def run_chat(answer_fn: Callable[[str, WorkingMemory], tuple[str, list[dict]]]) -> None:
    """The interactive loop. `answer_fn` is passed in so tests can replace it."""
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
            try:
                _handle_chat_command(query, working)
            except SchemaError as exc:
                _report_database_error(exc)
            continue
        try:
            response, used_memories = answer_fn(query, working)
        except SchemaError as exc:
            _report_database_error(exc)
            continue
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