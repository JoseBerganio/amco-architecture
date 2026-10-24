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

"""Contract: the Ollama request and its error messages must match v0.2.0 exactly."""

import httpx
import pytest

import amco.models.ollama as model

URL = "http://localhost:11434/api/chat"
MESSAGES = [
    {"role": "system", "content": "s"},
    {"role": "user", "content": "q"},
]


def _response(status: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", URL)
    return httpx.Response(status, request=request, **kwargs)


def _patch_post(monkeypatch, result, captured: dict | None = None) -> None:
    def post(url, json, timeout):
        if captured is not None:
            captured.update(url=url, json=json, timeout=timeout)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(model.httpx, "post", post)


def _clean_env(monkeypatch) -> None:
    for name in (
        "AMCO_MODEL", "AMCO_OLLAMA_URL", "AMCO_CONTEXT_TOKENS",
        "AMCO_TIMEOUT_SECONDS", "AMCO_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_request_is_exactly_the_v020_request(monkeypatch):
    _clean_env(monkeypatch)
    captured: dict = {}
    _patch_post(monkeypatch, _response(200, json={"message": {"content": "hi"}}), captured)

    assert model.OllamaChat().chat(MESSAGES) == "hi"
    assert captured == {
        "url": "http://localhost:11434/api/chat",
        "json": {
            "model": "qwen2.5:3b",
            "messages": MESSAGES,
            "stream": False,
            "options": {"num_ctx": 4096},
        },
        "timeout": 300.0,
    }


def test_settings_change_the_request(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("AMCO_MODEL", "llama3.2")
    monkeypatch.setenv("AMCO_OLLAMA_URL", "http://example.test:9999/")
    monkeypatch.setenv("AMCO_CONTEXT_TOKENS", "2048")
    monkeypatch.setenv("AMCO_TIMEOUT_SECONDS", "42")
    captured: dict = {}
    _patch_post(monkeypatch, _response(200, json={"message": {"content": "ok"}}), captured)

    model.OllamaChat().chat(MESSAGES)
    assert captured["url"] == "http://example.test:9999/api/chat"
    assert captured["json"]["model"] == "llama3.2"
    assert captured["json"]["options"] == {"num_ctx": 2048}
    assert captured["timeout"] == 42.0


def test_explicit_timeout_wins(monkeypatch):
    _clean_env(monkeypatch)
    captured: dict = {}
    _patch_post(monkeypatch, _response(200, json={"message": {"content": "ok"}}), captured)
    model.OllamaChat().chat(MESSAGES, timeout=5.0)
    assert captured["timeout"] == 5.0


def _error_text(monkeypatch, result) -> str:
    _clean_env(monkeypatch)
    _patch_post(monkeypatch, result)
    with pytest.raises(RuntimeError) as exc_info:
        model.OllamaChat().chat(MESSAGES)
    return str(exc_info.value)


def test_connection_error_message(monkeypatch):
    text = _error_text(monkeypatch, httpx.ConnectError("boom"))
    assert text == (
        "Cannot connect to Ollama at http://localhost:11434. "
        "Start Ollama and confirm it is running."
    )


def test_missing_model_message(monkeypatch):
    text = _error_text(monkeypatch, _response(404, text="model not found"))
    assert text == "Model 'qwen2.5:3b' was not found. Run: ollama pull qwen2.5:3b"


def test_http_error_message_is_cut_at_500_characters(monkeypatch):
    text = _error_text(monkeypatch, _response(500, text="x" * 600))
    assert text == "Ollama returned HTTP 500: " + "x" * 500


def test_other_transport_error_message(monkeypatch):
    text = _error_text(monkeypatch, httpx.ReadTimeout("slow"))
    assert text == "Ollama request failed: slow"


def test_unexpected_response_format_message(monkeypatch):
    expected = "Ollama returned an unexpected response format."
    assert _error_text(monkeypatch, _response(200, json={"unexpected": 1})) == expected
    assert _error_text(monkeypatch, _response(200, text="not json")) == expected