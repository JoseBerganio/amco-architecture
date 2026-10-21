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

import httpx

from ..config import context_settings, model_name, ollama_url, timeout_seconds
from .base import ModelError


class OllamaChat:
    """Chat adapter for a local Ollama server."""

    @property
    def name(self) -> str:
        return model_name()

    def chat(self, messages: list[dict[str, str]], timeout: float | None = None) -> str:
        base_url = ollama_url()
        model = model_name()
        context_limit, _, _ = context_settings()
        if timeout is None:
            timeout = timeout_seconds()

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": context_limit},
        }
        try:
            response = httpx.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ModelError(
                f"Cannot connect to Ollama at {base_url}. Start Ollama and confirm it is running."
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' was not found. Run: ollama pull {model}"
                ) from exc
            detail = exc.response.text[:500]
            raise ModelError(
                f"Ollama returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(f"Ollama request failed: {exc}") from exc

        try:
            return response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ModelError("Ollama returned an unexpected response format.") from exc