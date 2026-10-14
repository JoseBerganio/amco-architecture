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

import os

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

DEFAULT_CONTEXT_TOKENS = 4096
DEFAULT_RESERVED_OUTPUT_TOKENS = 512
DEFAULT_MEMORY_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 300


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


def context_settings() -> tuple[int, int, int]:
    """Return (context limit, reserved output tokens, memory token cap)."""
    return (
        int_env("AMCO_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS),
        int_env("AMCO_RESERVED_OUTPUT_TOKENS", DEFAULT_RESERVED_OUTPUT_TOKENS),
        int_env("AMCO_MEMORY_TOKENS", DEFAULT_MEMORY_TOKENS),
    )
