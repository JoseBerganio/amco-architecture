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
from rich.markup import escape
from rich.table import Table

from ..lifecycle import apply_finding, review
from ..storage import (
    add_memory,
    check_duplicates,
    delete_memory,
    get_memory,
    list_memories,
    rebuild_index,
    restore_memory,
    search_memories,
    supersede_memory,
    update_memory,
)
from .common import (
    CONFIDENCE_HELP,
    TYPE_HELP,
    _status_label,
    console,
    err_console,
    handle_schema_errors,
  )

memory_app = typer.Typer(help="Manage stored memories.", no_args_is_help=True)


@memory_app.command("add")
@handle_schema_errors
def memory_add(
    content: str = typer.Argument(..., help="Text to save as a memory."),
    category: str = typer.Option("general", "--category", "-c", help="Memory category."),
    memory_type: str = typer.Option("persistent", "--type", "-t", help=TYPE_HELP),
    confidence: float = typer.Option(1.0, "--confidence", min=0.0, max=1.0, help=CONFIDENCE_HELP),
    expires: Optional[str] = typer.Option(
        None, "--expires", help="Last day this memory is valid (YYYY-MM-DD)."
    ),
    supersedes: Optional[int] = typer.Option(
        None, "--supersedes", min=1, help="ID of an older memory this one replaces."
    ),
    force: bool = typer.Option(False, "--force", help="Save even if an identical memory exists."),
) -> None:
    """Add an explicitly approved memory."""
    try:
        exact, similar = check_duplicates(content)
        if exact and not force:
            err_console.print(
                f"An identical memory already exists: #{exact['id']}. Use --force to save anyway."
            )
            raise typer.Exit(code=1)
        memory_id = add_memory(
            content,
            category,
            memory_type,
            confidence=confidence,
            expires_at=expires,
            supersedes=supersedes,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Saved memory [bold]#{memory_id}[/bold].")
    if supersedes is not None:
        console.print(f"Memory #{supersedes} is now superseded by #{memory_id}.")
    elif similar:
        console.print("[yellow]Similar memories already exist:[/yellow]")
        for item in similar:
            console.print(
                f"  #{item['id']} ({item['similarity']:.0%} similar) {item['content']}",
                markup=False,
                highlight=False,
            )
        console.print(
            f"If this replaces one, run: amco memory supersede <old-id> {memory_id}",
            markup=False,
        )


@memory_app.command("list")
@handle_schema_errors
def memory_list(
    memory_type: Optional[str] = typer.Option(None, "--type", "-t", help=TYPE_HELP),
    show_all: bool = typer.Option(
        False, "--all", help="Include superseded and expired memories."
    ),
) -> None:
    """List stored memories."""
    try:
        records = list_memories(memory_type=memory_type, include_inactive=show_all)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not records:
        console.print("No memories stored yet.")
        return
    columns = ["ID", "Type", "Category", "Conf", "Updated", "Content"]
    if show_all:
        columns.insert(1, "Status")
    table = Table(*columns)
    for item in records:
        row = [
            str(item["id"]),
            item["memory_type"],
            escape(item["category"]),
            f"{item['confidence']:.2f}",
            item["updated_at"] or item["created_at"],
            escape(item["content"]),
        ]
        if show_all:
            row.insert(1, _status_label(item))
        table.add_row(*row)
    console.print(table)


@memory_app.command("inspect")
@handle_schema_errors
def memory_inspect(
    memory_id: int = typer.Argument(..., min=1, help="Memory ID."),
) -> None:
    """Show a memory's full content and metadata."""
    item = get_memory(memory_id)
    if item is None:
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)
    console.print(f"[bold]Memory #{item['id']}[/bold]")
    console.print(f"  Status:     {_status_label(item)}")
    console.print(f"  Type:       {item['memory_type']}")
    console.print(f"  Category:   {item['category']}")
    console.print(f"  Source:     {item['source']}")
    console.print(f"  Confidence: {item['confidence']:.2f}")
    console.print(f"  Used:       {item['use_count']} times in prompts")
    console.print(f"  Last used:  {item['last_used_at'] or '(never)'}")
    console.print(f"  Expires:    {item['expires_at'] or '(never)'}")
    console.print(f"  Created:    {item['created_at']}")
    console.print(f"  Updated:    {item['updated_at']}")
    console.print("  Content:")
    console.print(f"    {item['content']}", markup=False)


@memory_app.command("update")
@handle_schema_errors
def memory_update(
    memory_id: int = typer.Argument(..., min=1, help="Memory ID."),
    content: Optional[str] = typer.Option(None, "--content", help="New content."),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="New category."),
    memory_type: Optional[str] = typer.Option(None, "--type", "-t", help=TYPE_HELP),
    confidence: Optional[float] = typer.Option(
        None, "--confidence", min=0.0, max=1.0, help=CONFIDENCE_HELP
    ),
    expires: Optional[str] = typer.Option(
        None, "--expires", help="New expiry date (YYYY-MM-DD), or 'none' to clear it."
    ),
) -> None:
    """Update a memory's content, category, type, confidence, or expiry."""
    try:
        updated = update_memory(
            memory_id, content, category, memory_type, confidence=confidence, expires_at=expires
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not updated:
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)
    console.print(f"Updated memory [bold]#{memory_id}[/bold].")


@memory_app.command("supersede")
@handle_schema_errors
def memory_supersede(
    old_id: int = typer.Argument(..., min=1, help="Memory being replaced."),
    new_id: int = typer.Argument(..., min=1, help="Memory that replaces it."),
) -> None:
    """Mark a memory as replaced by another. It is hidden from chat but kept."""
    try:
        done = supersede_memory(old_id, new_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not done:
        err_console.print(f"No memory found with ID #{old_id}.")
        raise typer.Exit(code=1)
    console.print(f"Memory #{old_id} is now superseded by #{new_id}.")


@memory_app.command("restore")
@handle_schema_errors
def memory_restore(
    memory_id: int = typer.Argument(..., min=1, help="Memory ID."),
) -> None:
    """Bring a superseded memory back into use."""
    if not restore_memory(memory_id):
        err_console.print(f"No memory found with ID #{memory_id}.")
        raise typer.Exit(code=1)
    console.print(f"Restored memory #{memory_id}.")


@memory_app.command("review")
@handle_schema_errors
def memory_review(
    apply: bool = typer.Option(False, "--apply", help="Carry out the suggested changes."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation with --apply."),
) -> None:
    """Review memory health: expired, superseded, duplicate, stale, and well-used memories."""
    findings = review()
    if not findings:
        console.print("Nothing to review. Memory looks healthy.")
        return
    table = Table("ID", "Action", "Reason")
    for f in findings:
        action = f"supersede -> #{f.target_id}" if f.action == "supersede" else f.action
        table.add_row(str(f.memory_id), action, f.reason)
    console.print(table)
    if not apply:
        console.print("Nothing was changed. Run again with --apply to carry these out.")
        return
    if not yes and not typer.confirm(f"Apply {len(findings)} change(s)?", default=False):
        console.print("Cancelled.")
        raise typer.Exit()
    done = 0
    for f in findings:
        try:
            if apply_finding(f):
                done += 1
        except ValueError as exc:
            err_console.print(f"Skipped #{f.memory_id}: {exc}")
    console.print(f"Applied {done} of {len(findings)} change(s).")


@memory_app.command("search")
@handle_schema_errors
def memory_search(
    query: str = typer.Argument(..., help="Words to search for."),
    limit: int = typer.Option(5, min=1, max=50, help="Maximum results."),
    explain: bool = typer.Option(False, "--explain", help="Show how each result was scored."),
) -> None:
    """Full-text search over active memories, ranked by relevance, confidence, freshness and usefulness."""
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
@handle_schema_errors
def memory_reindex() -> None:
    """Rebuild the full-text search index from the stored memories."""
    if rebuild_index():
        console.print("Search index rebuilt.")
    else:
        err_console.print("Full-text search (FTS5) is not available in this SQLite build.")
        raise typer.Exit(code=1)


@memory_app.command("delete")
@handle_schema_errors
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
