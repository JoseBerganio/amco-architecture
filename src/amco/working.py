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

from dataclasses import dataclass, field


def estimate_tokens(text: str) -> int:
    """Rough token estimate (about 4 characters per token)."""
    return (len(text) + 3) // 4 if text else 0


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class WorkingMemory:
    """Short-lived state for the current chat session."""

    turns: list[Turn] = field(default_factory=list)
    task: str | None = None
    dropped_turns: int = 0
    last_prompt_tokens: int = 0
    last_report: object | None = None #AME diagnostics, shown by /why

    @property
    def tokens(self) -> int:
        return sum(estimate_tokens(turn.content) for turn in self.turns)

    def add(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Role must be 'user' or 'assistant'.")
        self.turns.append(Turn(role, content))

    def set_task(self, task: str | None) -> None:
        task = task.strip() if task else None
        self.task = task or None

    def messages(self) -> list[dict[str, str]]:
        return [{"role": turn.role, "content": turn.content} for turn in self.turns]

    def trim(self, budget_tokens: int) -> int:
        """Drop the oldest whole turns until history fits the budget.

        The remaining history always starts with a user turn. Returns the
        number of turns removed.
        """
        removed = 0
        total = self.tokens
        while self.turns and total > budget_tokens:
            total -= estimate_tokens(self.turns.pop(0).content)
            removed += 1
        while self.turns and self.turns[0].role != "user":
            self.turns.pop(0)
            removed += 1
        self.dropped_turns += removed
        return removed

    def clear(self) -> None:
        self.turns.clear()
        self.task = None
        self.dropped_turns = 0
        self.last_prompt_tokens = 0
        self.last_report = None