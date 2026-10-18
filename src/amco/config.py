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
import os

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

DEFAULT_CONTEXT_TOKENS = 4096
DEFAULT_RESERVED_OUTPUT_TOKENS = 512
DEFAULT_MEMORY_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 300

DEFAULT_FRESHNESS_HALF_LIFE_DAYS = 180.0
DEFAULT_FOLLOWUP_MIN_TERMS = 3
DEFAULT_FOLLOWUP_TURNS = 2

DEFAULT_STALE_DAYS = 90
DEFAULT_PROMOTE_USES = 5
DEFAULT_SUPERSEDED_RETENTION_DAYS = 30

def model_name() -> str:
    return os.getenv("AMCO_MODEL", DEFAULT_MODEL)


def ollama_url() -> str:
    return os.getenv("AMCO_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")


def int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def float_env(name: str, default: float) -> float:
    """Read a non-negative, finite float from the environment."""
    try:
        value = float(os.getenv(name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= 0 else default


def context_settings() -> tuple[int, int, int]:
    """Return (context limit, reserved output tokens, memory token cap)."""
    return (
        int_env("AMCO_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS),
        int_env("AMCO_RESERVED_OUTPUT_TOKENS", DEFAULT_RESERVED_OUTPUT_TOKENS),
        int_env("AMCO_MEMORY_TOKENS", DEFAULT_MEMORY_TOKENS),
    )


def freshness_half_life_days() -> float:
    value = float_env("AMCO_FRESHNESS_HALF_LIFE_DAYS", DEFAULT_FRESHNESS_HALF_LIFE_DAYS)
    return value if value > 0 else DEFAULT_FRESHNESS_HALF_LIFE_DAYS


def followup_settings() -> tuple[int, int]:
    """Return (min meaningful terms before history is skipped, user turns to borrow)."""
    return (
        int_env("AMCO_FOLLOWUP_MIN_TERMS", DEFAULT_FOLLOWUP_MIN_TERMS),
        int_env("AMCO_FOLLOWUP_TURNS", DEFAULT_FOLLOWUP_TURNS),
    )
    

def lifecycle_settings() -> tuple[int, int, int]:
    """Return (idle days before archiving, uses before promotion, days to keep superseded memories)."""
    return (
        int_env("AMCO_STALE_DAYS", DEFAULT_STALE_DAYS),
        int_env("AMCO_PROMOTE_USES", DEFAULT_PROMOTE_USES),
        int_env("AMCO_SUPERSEDED_RETENTION_DAYS", DEFAULT_SUPERSEDED_RETENTION_DAYS),
    )    
    