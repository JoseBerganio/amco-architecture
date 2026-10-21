"""Compatibility shim, removed in Sprint 9. New code should use amco.models.OllamaChat."""

from __future__ import annotations

import httpx  # noqa: F401  (existing tests patch model.httpx.post)

from .models.ollama import OllamaChat


def ollama_chat(messages: list[dict[str, str]], timeout: float | None = None) -> str:
    return OllamaChat().chat(messages, timeout=timeout)