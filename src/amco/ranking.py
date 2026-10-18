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

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import float_env, freshness_half_life_days

# Prior for how reusable each memory type tends to be.
TYPE_PRIORS = {"persistent": 1.0, "long_term": 0.6}
USAGE_CAP = 10  # uses at which the usage signal saturates


@dataclass(frozen=True)
class RankingWeights:
    relevance: float = 0.65
    confidence: float = 0.15
    freshness: float = 0.05
    usefulness: float = 0.15


def weights_from_env() -> RankingWeights:
    d = RankingWeights()
    return RankingWeights(
        relevance=float_env("AMCO_WEIGHT_RELEVANCE", d.relevance),
        confidence=float_env("AMCO_WEIGHT_CONFIDENCE", d.confidence),
        freshness=float_env("AMCO_WEIGHT_FRESHNESS", d.freshness),
        usefulness=float_env("AMCO_WEIGHT_USEFULNESS", d.usefulness),
    )


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def freshness(updated_at: Any, now: datetime, half_life_days: float) -> float:
    """1.0 for brand-new memories, 0.5 after one half-life. Unknown dates score 0.5."""
    stamp = parse_timestamp(updated_at)
    if stamp is None:
        return 0.5
    age_days = max(0.0, (now - stamp).total_seconds() / 86400)
    return 0.5 ** (age_days / half_life_days)


def usefulness(memory_type: str, use_count: int, history: bool = False) -> float:
    prior = 1.0 if history else TYPE_PRIORS.get(memory_type, 0.5)
    usage = min(1.0, math.log1p(max(0, int(use_count or 0))) / math.log1p(USAGE_CAP))
    return 0.5 * prior + 0.5 * usage


def rank_memories(
    candidates: list[dict[str, Any]],
    weights: RankingWeights | None = None,
    now: datetime | None = None,
    history: bool = False,
) -> list[dict[str, Any]]:
    """Score and sort candidates (best first).

    Each candidate needs a positive `match_score` from retrieval. Returned
    copies gain `score` and `score_parts` (R, C, F, U) so results can be explained.
    """
    if not candidates:
        return []
    weights = weights or weights_from_env()
    now = now or datetime.now(timezone.utc)
    half_life = freshness_half_life_days()
    best_match = max(float(c.get("match_score", 0.0)) for c in candidates)

    ranked = []
    for c in candidates:
        match = float(c.get("match_score", 0.0))
        parts = {
            "relevance": match / best_match if best_match > 0 else 1.0,
            "confidence": min(1.0, max(0.0, float(c.get("confidence", 1.0)))),
            "freshness": freshness(c.get("updated_at"), now, half_life),
            "usefulness": usefulness(c.get("memory_type", "persistent"), c.get("use_count", 0), history),
        }
        score = (
            weights.relevance * parts["relevance"]
            + weights.confidence * parts["confidence"]
            + weights.freshness * parts["freshness"]
            + weights.usefulness * parts["usefulness"]
        )
        ranked.append({**c, "score": score, "score_parts": parts})

    ranked.sort(key=lambda m: (m["score"], m["id"]), reverse=True)
    return ranked