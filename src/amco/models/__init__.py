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

from ..config import provider_name
from .base import ChatModel, ModelError
from .ollama import OllamaChat

PROVIDERS = {"ollama": OllamaChat}


def get_model() -> ChatModel:
    """Return the adapter selected by AMCO_PROVIDER (default: ollama)."""
    provider = provider_name()
    factory = PROVIDERS.get(provider)
    if factory is None:
        available = ", ".join(sorted(PROVIDERS))
        raise ModelError(
            f"Unknown model provider '{provider}'. "
            f"Available providers: {available}. Set AMCO_PROVIDER to one of them."
        )
    return factory()


__all__ = ["ChatModel", "ModelError", "OllamaChat", "PROVIDERS", "get_model"]