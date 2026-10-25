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

from .. import __version__
from ..storage import database_path, session
from .common import console, handle_schema_errors


def version() -> None:
    """Show AMCO version."""
    console.print(f"AMCO {__version__}")

@handle_schema_errors
def init() -> None:
    """Initialize the local workspace and SQLite database."""
    path = database_path()
    with session(path):
        pass
    console.print(f"[green]AMCO initialized.[/green] Database: {path}")