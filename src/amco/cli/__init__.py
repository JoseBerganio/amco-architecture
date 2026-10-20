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

import typer

from ..engine import answer
from .chat import run_chat
from .memory import memory_app
from .system import init, version

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