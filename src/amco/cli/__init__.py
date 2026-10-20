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

from ..config import model_name
from .. import __version__
from ..engine import answer, context_settings
from ..lifecycle import apply_finding, review
from .common import CONFIDENCE_HELP, TYPE_HELP, _status_label, console, err_console
from .system import init, version
from .memory import memory_app
from .chat import run_chat
from ..storage import (
    VALID_TYPES,
    add_memory,
    check_duplicates,
    database_path,
    delete_memory,
    get_memory,
    list_memories,
    memory_status,
    rebuild_index,
    restore_memory,
    search_memories,
    session,
    supersede_memory,
    update_memory,
)
from ..working import WorkingMemory


app = typer.Typer(help="AMCO — Adaptive Memory Controller", no_args_is_help=True)

app.add_typer(memory_app, name="memory")



@app.callback()
def main() -> None:
    """AMCO local-first memory orchestration prototype."""
    
app.command()(version)
app.command()(init)


@app.command()
def chat() -> None:
    """Start a memory-enabled interactive chat with Ollama."""
    run_chat(answer)