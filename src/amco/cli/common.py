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

import functools
from typing import Any, Callable

import typer
from rich.console import Console

from ..storage import VALID_KINDS, VALID_TYPES, SchemaError, memory_status

console = Console()
err_console = Console(stderr=True)

TYPE_HELP = f"Memory type: {' or '.join(VALID_TYPES)}."
ADD_TYPE_HELP = (
    f"Memory type: {' or '.join(VALID_TYPES)}. "
    "Default: persistent for facts, long_term for summaries and records."
)
KIND_HELP = f"Memory kind: {', '.join(VALID_KINDS[:-1])} or {VALID_KINDS[-1]}."
CONFIDENCE_HELP = "Confidence from 0 to 1 (1 = confirmed)."


def _status_label(item: dict) -> str:
    status = memory_status(item)
    return f"superseded by #{item['superseded_by']}" if status == "superseded" else status


def period_text(item: dict) -> str:
    """The period of a memory as one line, for `memory inspect`."""
    start, end = item.get("period_start"), item.get("period_end")
    if start and end:
        return f"{start} to {end}"
    if start:
        return f"from {start}"
    if end:
        return f"until {end}"
    return "(none)"


def handle_schema_errors(command: Callable[..., Any]) -> Callable[..., Any]:
    """Turn a SchemaError into a one-line message and exit code 1, instead of a traceback.

    Apply it directly under @memory_app.command(...) on every command that
    opens the database. functools.wraps keeps the name, docstring and
    signature, so Typer builds the same command (the CLI contract test proves it).
    """

    @functools.wraps(command)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return command(*args, **kwargs)
        except SchemaError as exc:
            err_console.print(str(exc), markup=False, highlight=False)
            raise typer.Exit(code=1) from exc

    return wrapper