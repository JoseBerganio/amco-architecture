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

"""Pass/fail thresholds for `amco eval run`. Pure: no files, no Rich."""

from __future__ import annotations

from .results import Summary

_EPS = 1e-9


def check_gates(
    summary: Summary,
    min_recall: float | None = None,
    min_mrr: float | None = None,
) -> list[str]:
    """Reasons the run fails its thresholds. An empty list means it passes.

    Gates judge the candidates view (retrieval quality in the top k). A metric
    that is undefined, for example because every selected query is negative,
    cannot meet a threshold.
    """
    checks = (
        ("candidate recall", summary.candidates.recall, min_recall),
        ("candidate MRR", summary.candidates.mrr, min_mrr),
    )
    failures: list[str] = []
    for label, actual, minimum in checks:
        if minimum is None:
            continue
        if actual is None:
            failures.append(
                f"Gate failed: {label} is undefined (no selected query expects a memory), "
                f"so the required {minimum:.3f} cannot be met."
            )
        elif actual + _EPS < minimum:
            failures.append(
                f"Gate failed: {label} {actual:.3f} is below the required {minimum:.3f}."
            )
    return failures