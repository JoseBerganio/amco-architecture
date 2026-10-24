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

import ast
from pathlib import Path

import httpx
import pytest

import amco.ame as ame_module
import amco.engine as engine
import amco.models as models_package
from amco.models import ChatModel, ModelError, OllamaChat, get_model
from amco.working import WorkingMemory

from types import SimpleNamespace

URL = "http://localhost:11434/api/chat"
MESSAGES = [{"role": "user", "content": "hello"}]


class FakeModel:
    name = "fake"

    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.reply


class FailingModel:
    name = "failing"

    def chat(self, messages):
        raise ModelError("down")


def _response(status: int, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", URL), **kwargs)


def _patch_post(monkeypatch, result, captured: dict | None = None) -> None:
    def post(url, json, timeout):
        if captured is not None:
            captured.update(url=url, json=json, timeout=timeout)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(httpx, "post", post)


def _clean_env(monkeypatch) -> None:
    for name in (
        "AMCO_MODEL", "AMCO_OLLAMA_URL", "AMCO_CONTEXT_TOKENS",
        "AMCO_TIMEOUT_SECONDS", "AMCO_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)


# --- Contract and factory ---------------------------------------------------


def test_model_error_is_a_runtime_error():
    assert issubclass(ModelError, RuntimeError)


def test_adapters_satisfy_the_chat_model_contract(monkeypatch):
    _clean_env(monkeypatch)
    assert isinstance(OllamaChat(), ChatModel)
    assert isinstance(FakeModel(), ChatModel)


def test_default_provider_is_ollama(monkeypatch):
    _clean_env(monkeypatch)
    assert isinstance(get_model(), OllamaChat)


def test_provider_name_ignores_case_and_spaces(monkeypatch):
    monkeypatch.setenv("AMCO_PROVIDER", "  Ollama ")
    assert isinstance(get_model(), OllamaChat)


def test_unknown_provider_gives_a_clear_error(monkeypatch):
    monkeypatch.setenv("AMCO_PROVIDER", "nope")
    with pytest.raises(ModelError) as exc_info:
        get_model()
    message = str(exc_info.value)
    assert "Unknown model provider 'nope'" in message
    assert "ollama" in message
    assert "AMCO_PROVIDER" in message


def test_adapter_name_is_read_at_call_time(monkeypatch):
    adapter = OllamaChat()
    monkeypatch.setenv("AMCO_MODEL", "first")
    assert adapter.name == "first"
    monkeypatch.setenv("AMCO_MODEL", "second")
    assert adapter.name == "second"


# --- OllamaChat honors settings and raises ModelError -----------------------


def test_adapter_honors_model_url_context_and_timeout(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("AMCO_MODEL", "llama3.2")
    monkeypatch.setenv("AMCO_OLLAMA_URL", "http://example.test:9999/")
    monkeypatch.setenv("AMCO_CONTEXT_TOKENS", "2048")
    monkeypatch.setenv("AMCO_TIMEOUT_SECONDS", "42")
    captured: dict = {}
    _patch_post(monkeypatch, _response(200, json={"message": {"content": "ok"}}), captured)

    assert OllamaChat().chat(MESSAGES) == "ok"
    assert captured["url"] == "http://example.test:9999/api/chat"
    assert captured["json"]["model"] == "llama3.2"
    assert captured["json"]["options"]["num_ctx"] == 2048
    assert captured["timeout"] == 42.0


def test_adapter_explicit_timeout_wins(monkeypatch):
    _clean_env(monkeypatch)
    captured: dict = {}
    _patch_post(monkeypatch, _response(200, json={"message": {"content": "ok"}}), captured)
    OllamaChat().chat(MESSAGES, timeout=7.5)
    assert captured["timeout"] == 7.5


def test_adapter_connection_failure_is_a_model_error(monkeypatch):
    _clean_env(monkeypatch)
    _patch_post(monkeypatch, httpx.ConnectError("boom"))
    with pytest.raises(ModelError, match="Cannot connect to Ollama"):
        OllamaChat().chat(MESSAGES)


def test_adapter_missing_model_gives_a_pull_hint(monkeypatch):
    _clean_env(monkeypatch)
    _patch_post(monkeypatch, _response(404, text="model not found"))
    with pytest.raises(ModelError) as exc_info:
        OllamaChat().chat(MESSAGES)
    assert "ollama pull qwen2.5:3b" in str(exc_info.value)


# --- Engine wiring ----------------------------------------------------------


def _use_temp_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AMCO_DB_PATH", str(tmp_path / "t.sqlite3"))


def test_answer_uses_an_injected_model(tmp_path: Path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    def must_not_run():
        raise AssertionError("get_model must not be called when a model is injected")

    monkeypatch.setattr(engine, "get_model", must_not_run)
    fake = FakeModel("hello from the fake")
    working = WorkingMemory()

    response, used = engine.answer("What is the project codename?", working, model=fake)

    assert response == "hello from the fake"
    assert used == []
    assert len(fake.calls) == 1
    assert fake.calls[0][0]["role"] == "system"
    assert fake.calls[0][-1] == {"role": "user", "content": "What is the project codename?"}
    assert len(working.turns) == 2


def test_failed_injected_model_records_nothing(tmp_path: Path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    working = WorkingMemory()
    with pytest.raises(ModelError):
        engine.answer("hello there", working, model=FailingModel())
    assert working.turns == []


def test_answer_without_a_model_uses_the_configured_adapter(tmp_path: Path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    seen = {}

    def fake_chat(messages):
        seen["messages"] = messages
        return "via the seam"

    monkeypatch.setattr(engine, "get_model", lambda: SimpleNamespace(chat=fake_chat))
    response, _ = engine.answer("hello there")
    assert response == "via the seam"
    assert seen["messages"][-1]["content"] == "hello there"


def test_unknown_provider_surfaces_as_a_runtime_error_from_answer(tmp_path: Path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    monkeypatch.setenv("AMCO_PROVIDER", "nope")
    with pytest.raises(RuntimeError, match="Unknown model provider"):
        engine.answer("hello there")


# --- Layering ---------------------------------------------------------------


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add("." * node.level + (node.module or ""))
    return found


@pytest.mark.parametrize("module", [engine, ame_module])
def test_engine_and_ame_do_not_import_ollama_or_httpx(module):
    imported = _imported_modules(Path(module.__file__))
    assert not imported & {"httpx", ".model", ".models.ollama"}


@pytest.mark.parametrize("filename", ["__init__.py", "base.py", "ollama.py"])
def test_models_package_depends_only_on_config(filename):
    folder = Path(models_package.__file__).parent
    for name in _imported_modules(folder / filename):
        if name.startswith(".."):
            assert name == "..config", f"models/{filename} imports {name}"