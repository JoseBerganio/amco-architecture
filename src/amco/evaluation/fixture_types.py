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

"""Plain data for evaluation fixtures. No I/O and no validation logic lives here."""

from __future__ import annotations

from dataclasses import dataclass


class FixtureError(ValueError):
    """A fixture file is missing, unreadable, or breaks a fixture rule."""


# The kinds ame.analyze_task() can return. Kept here so fixtures can label queries.
TASK_KINDS = ("chitchat", "followup", "instruction", "question", "statement")
VALID_SPLITS = ("train", "dev")
VALID_ROLES = ("user", "assistant")

# A typo in a tag would silently drop a query from its per-tag report, so tags are closed.
# Later sprints add theirs here (Sprint 11 adds "ltm").
KNOWN_TAGS = frozenset(
    {
        "exact", "stem", "multi-term", "paraphrase",
        "followup", "assistant-followup", "history",
        "superseded", "expired", "duplicate", "conflict",
        "negative", "chitchat",
    }
)


@dataclass(frozen=True)
class FixtureMemory:
    key: str                          # stable name; fixtures never use database IDs
    content: str
    category: str = "general"
    memory_type: str = "persistent"
    confidence: float = 1.0
    age_days: int = 0                 # backdates created_at/updated_at when the DB is built
    expires_in_days: int | None = None  # relative to the run date; negative = already expired
    supersedes: str | None = None     # key of an OLDER memory this one replaces
    use_count: int = 0


@dataclass(frozen=True)
class FixtureTurn:
    role: str                         # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class FixtureQuery:
    id: str
    query: str
    expect: tuple[str, ...] = ()      # keys that SHOULD be retrieved (empty for negatives)
    forbid: tuple[str, ...] = ()      # keys that must NOT be selected
    history: bool = False             # labels a history question; the runner checks it later
    turns: tuple[FixtureTurn, ...] = ()  # earlier chat turns used to seed Working Memory
    task: str | None = None           # pinned task, as set by /task
    tags: tuple[str, ...] = ()
    expect_kind: str | None = None    # classifier check (see TASK_KINDS)
    split: str | None = None          # "train" or "dev" (used for tuning in Sprint 13)


@dataclass(frozen=True)
class FixtureSet:
    name: str
    description: str
    memories: tuple[FixtureMemory, ...]
    queries: tuple[FixtureQuery, ...]

    def memory_keys(self) -> list[str]:
        return [m.key for m in self.memories]