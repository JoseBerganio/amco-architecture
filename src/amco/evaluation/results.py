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

"""Plain data produced by an evaluation run. No logic lives here."""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import Distribution, Ratio


@dataclass(frozen=True)
class Observation:
    """What the AME did for one query, with database IDs already turned into fixture keys."""
    kind: str                                   # task kind the classifier chose
    wants_history: bool                         # history cues detected
    borrowed: bool                              # search text borrowed from task or earlier turns
    depth: int                                  # how many memories the AME considered
    search_text: str
    candidates: tuple[str, ...]                 # ranked, before duplicate removal
    selected: tuple[str, ...]                   # what reached the prompt
    skipped: tuple[tuple[str, str], ...]        # (key, reason)
    conflicts: tuple[tuple[str, str], ...]      # (preferred key, other key)
    memory_tokens: int
    prompt_tokens: int
    retrieval_ms: float
    total_ms: float


@dataclass(frozen=True)
class ViewScores:
    """Retrieval metrics for one view (candidates or selected). None means undefined."""

    recall: float | None
    hit: bool | None
    reciprocal_rank: float | None
    precision: float | None


@dataclass(frozen=True)
class QueryResult:
    id: str
    query: str
    tags: tuple[str, ...]
    split: str | None
    expect: tuple[str, ...]
    forbid: tuple[str, ...]
    expect_kind: str | None
    observation: Observation
    candidates: ViewScores                      # cut at k
    selected: ViewScores                        # whole selected list
    forbidden_selected: tuple[str, ...]
    false_inclusion: bool | None                # only defined when nothing was expected
    kind_ok: bool | None                        # only defined when expect_kind is set
    history_ok: bool


@dataclass(frozen=True)
class ViewSummary:
    hits: Ratio                                 # queries where every expected key was found
    recall: float | None                        # mean over queries that expect something
    mrr: float | None
    precision: float | None                     # mean over queries that returned something


@dataclass(frozen=True)
class Summary:
    queries: int
    candidates: ViewSummary
    selected: ViewSummary
    forbid_violations: Ratio                    # lower is better; over queries that set forbid
    false_inclusion: Ratio                      # lower is better; over queries expecting nothing
    classifier: Ratio                           # over queries with expect_kind
    history_labels: Ratio                       # fixture history flag vs detected cues
    memory_tokens: Distribution
    prompt_tokens: Distribution
    retrieval_ms: Distribution
    total_ms: Distribution


@dataclass(frozen=True)
class SuiteResult:
    fixture_name: str
    fixture_hash: str
    k: int
    results: tuple[QueryResult, ...]
    overall: Summary
    by_tag: dict[str, Summary]
    by_split: dict[str, Summary]