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

import httpx
import pytest

import amco.model as model


def _fake_post(captured: dict, response: httpx.Response):
    def post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return response

    return post


def _response(status: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    return httpx.Response(status, request=request, **kwargs)


def test_default_model_is_qwen(monkeypatch):
    monkeypatch.delenv("AMCO_MODEL", raising=False)
    monkeypatch.delenv("AMCO_CONTEXT_TOKENS", raising=False)
    captured: dict = {}
    reply = _response(200, json={"message": {"content": "hi"}})
    monkeypatch.setattr(model.httpx, "post", _fake_post(captured, reply))

    assert model.ollama_chat([{"role": "user", "content": "hello"}]) == "hi"
    assert captured["json"]["model"] == "qwen2.5:3b"
    assert captured["json"]["stream"] is False


def test_context_window_is_sent_to_ollama(monkeypatch):
    monkeypatch.setenv("AMCO_CONTEXT_TOKENS", "2048")
    captured: dict = {}
    reply = _response(200, json={"message": {"content": "ok"}})
    monkeypatch.setattr(model.httpx, "post", _fake_post(captured, reply))

    model.ollama_chat([{"role": "user", "content": "hello"}])
    assert captured["json"]["options"]["num_ctx"] == 2048


def test_missing_model_gives_pull_hint(monkeypatch):
    monkeypatch.delenv("AMCO_MODEL", raising=False)
    reply = _response(404, text="model not found")
    monkeypatch.setattr(model.httpx, "post", _fake_post({}, reply))

    with pytest.raises(RuntimeError) as exc_info:
        model.ollama_chat([{"role": "user", "content": "hello"}])
    assert "ollama pull qwen2.5:3b" in str(exc_info.value)