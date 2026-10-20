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

from rich.console import Console

from ..storage import VALID_TYPES, memory_status

console = Console()
err_console = Console(stderr=True)

TYPE_HELP = f"Memory type: {' or '.join(VALID_TYPES)}."
CONFIDENCE_HELP = "Confidence from 0 to 1 (1 = confirmed)."


def _status_label(item: dict) -> str:
    status = memory_status(item)
    return f"superseded by #{item['superseded_by']}" if status == "superseded" else status