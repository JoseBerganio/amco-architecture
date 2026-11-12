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

"""Retrieval metrics as pure functions over lists of memory keys.

Conventions (decided in Sprint 10b):
  * Undefined is None. A query that expects nothing has no recall, MRR or
    precision, so those functions return None and the aggregators skip it.
  * A "hit" means EVERY expected key appears within the top k.
  * Precision divides by the results actually returned, not by k.
  * A key repeated in a ranked list is counted once and uses one rank slot.

This module imports only the standard library on purpose.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


# --- Helpers -------------------------------------------------------------------


def _check_k(k: int) -> int:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a whole number of at least 1.")
    return k


def _dedupe(ranked: Sequence[str], limit: int | None = None) -> list[str]:
    """Keep first occurrences in order, stopping once `limit` distinct keys are held."""
    seen: set[str] = set()
    out: list[str] = []
    for key in ranked:
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
        if limit is not None and len(out) == limit:
            break
    return out


# --- Per-query retrieval metrics ---------------------------------------------------


def recall_at_k(expected: Iterable[str], ranked: Sequence[str], k: int) -> float | None:
    """Share of expected keys found in the top k. None if nothing was expected."""
    wanted = set(expected)
    if not wanted:
        return None
    top = set(_dedupe(ranked, _check_k(k)))
    return len(wanted & top) / len(wanted)


def is_hit(expected: Iterable[str], ranked: Sequence[str], k: int) -> bool | None:
    """True when every expected key is in the top k. None if nothing was expected."""
    recall = recall_at_k(expected, ranked, k)
    return None if recall is None else recall == 1.0


def reciprocal_rank(
    expected: Iterable[str], ranked: Sequence[str], k: int | None = None
) -> float | None:
    """1 / rank of the first expected key (0.0 if none found). None if nothing expected.

    With `k`, only the top k count; without it, the whole list does.
    """
    wanted = set(expected)
    if not wanted:
        return None
    order = _dedupe(ranked, None if k is None else _check_k(k))
    for rank, key in enumerate(order, start=1):
        if key in wanted:
            return 1.0 / rank
    return 0.0


def precision_at_k(expected: Iterable[str], ranked: Sequence[str], k: int) -> float | None:
    """Share of the returned top-k results that were expected.

    None if nothing was expected or nothing was returned.
    """
    wanted = set(expected)
    top = _dedupe(ranked, _check_k(k))
    if not wanted or not top:
        return None
    return sum(key in wanted for key in top) / len(top)


# --- What actually reached the prompt ------------------------------------------------


def forbidden_hits(forbid: Iterable[str], selected: Sequence[str]) -> list[str]:
    """Forbidden keys that were selected, in selection order, each listed once."""
    banned = set(forbid)
    return [key for key in _dedupe(selected) if key in banned]


def has_false_inclusion(selected: Sequence[str]) -> bool:
    """True if anything was selected. Callers use this only for queries expecting nothing."""
    return len(selected) > 0


# --- Aggregation ------------------------------------------------------------------------


@dataclass(frozen=True)
class Ratio:
    """A rate that always carries its raw counts, for example 37/47 (78.7%)."""

    num: int
    den: int

    @property
    def value(self) -> float | None:
        return None if self.den == 0 else self.num / self.den

    def __str__(self) -> str:
        if self.den == 0:
            return "0/0 (n/a)"
        return f"{self.num}/{self.den} ({self.num / self.den:.1%})"


def ratio(flags: Iterable[bool | None]) -> Ratio:
    """Count True over all defined (non-None) flags."""
    defined = [f for f in flags if f is not None]
    return Ratio(sum(1 for f in defined if f), len(defined))


def mean_defined(values: Iterable[float | None]) -> float | None:
    """Mean of the values that are not None. None if there are none."""
    defined = [v for v in values if v is not None]
    return sum(defined) / len(defined) if defined else None


def percentile(values: Iterable[float], p: float) -> float | None:
    """The p-th percentile (0 to 100) by linear interpolation. None for no values."""
    if not 0 <= p <= 100:
        raise ValueError("Percentile must be between 0 and 100.")
    ordered = sorted(values)
    if not ordered:
        return None
    position = (p / 100) * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[low])
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


@dataclass(frozen=True)
class Distribution:
    """Summary of a numeric series such as latency or memory tokens."""

    count: int
    mean: float | None
    p50: float | None
    p95: float | None
    maximum: float | None


def describe(values: Iterable[float | None]) -> Distribution:
    defined = [v for v in values if v is not None]
    if not defined:
        return Distribution(0, None, None, None, None)
    return Distribution(
        count=len(defined),
        mean=sum(defined) / len(defined),
        p50=percentile(defined, 50),
        p95=percentile(defined, 95),
        maximum=float(max(defined)),
    )