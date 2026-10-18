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

"""Public chat entry point. The pipeline itself lives in ame.py."""

from __future__ import annotations

from . import ame
from .ame import SYSTEM_PROMPT, format_memory  # noqa: F401  (kept importable from here)
from .config import context_settings  # noqa: F401  (cli.py imports it from here)
from .model import ollama_chat
from .working import WorkingMemory


def select_memories(candidates: list[dict], budget_tokens: int) -> list[dict]:
    """Keep ranked candidates that fit the budget. Never truncates a memory."""
    return ame.select_within_budget(candidates, budget_tokens)[0]


def retrieval_query(query: str, working: WorkingMemory) -> str:
    """The text that will be searched for this message (see ame.analyze_task)."""
    return ame.analyze_task(query, working).retrieval_query


def answer(query: str, working: WorkingMemory | None = None) -> tuple[str, list[dict]]:
    """Answer a query using stored memories and (optionally) Working Memory.

    Without a WorkingMemory object the call is stateless, as in Sprint 1.
    """
    working = working if working is not None else WorkingMemory()
    prepared = ame.prepare(query, working)
    response = ollama_chat(prepared.messages)
    # Only record usage and the turn after the model call succeeds.
    ame.finish(prepared, query, response, working)
    return response, prepared.memories