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

"""Rules for session summaries kept in Long-Term Memory.

Sprint 11a holds the checks every summary must pass, whoever wrote it.
Sprint 11b adds draft_summary(), which asks the model for a draft.

Why a size limit: select_within_budget() skips a memory that does not fit the
memory budget and never truncates it, so an oversize summary would be saved
and then silently never retrieved. Refusing it at write time is kinder.
"""

from __future__ import annotations

from .working import estimate_tokens

MAX_SUMMARY_SHARE = 2  # one summary may use at most 1/2 of the memory budget


def summary_limit(context_limit: int, reserved_output: int, memory_cap: int) -> int:
    """The most tokens one summary may use.

    Mirrors the AME: memories get at most half of the usable context, capped by
    the memory-token setting. (The AME also subtracts the system prompt and the
    question, so this is slightly generous; the share keeps a safe margin.)
    """
    usable = max(0, context_limit - reserved_output)
    budget = min(memory_cap, usable // 2)
    return max(1, budget // MAX_SUMMARY_SHARE)


def check_summary(text: str, max_tokens: int) -> str:
    """Return the summary with whitespace collapsed, or raise ValueError.

    Collapsing newlines and tabs keeps a summary on one line, so stored text
    cannot imitate prompt sections.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        raise ValueError("A summary cannot be empty.")
    tokens = estimate_tokens(cleaned)
    if tokens > max_tokens:
        raise ValueError(
            f"That summary is too long (about {tokens} tokens; the limit is {max_tokens}, "
            "half of the memory budget). Shorten it, or split it into two summaries."
        )
    return cleaned


def _day(stamp: str | None) -> str | None:
    """The 'YYYY-MM-DD' part of a stored date or timestamp."""
    text = stamp.strip() if stamp else ""
    return text[:10] or None


def period_label(kind: str, period_start: str | None, period_end: str | None) -> str:
    """The kind and day(s) shown in a prompt line, for example 'summary 2026-11-19'.

    A period that spans days shows both ends: 'summary 2026-11-19..2026-11-21'.
    With no period only the kind is shown.
    """
    first, last = _day(period_start), _day(period_end)
    if first and last and first != last:
        return f"{kind} {first}..{last}"
    day = first or last
    return f"{kind} {day}" if day else kind