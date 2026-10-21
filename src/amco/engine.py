"""Public chat entry point. The pipeline itself lives in ame.py."""

from __future__ import annotations

from . import ame
from .ame import SYSTEM_PROMPT, format_memory  # noqa: F401  (kept importable from here)
from .config import context_settings  # noqa: F401  (cli/chat.py imports it from here)
from .models import ChatModel, get_model
from .working import WorkingMemory


def ollama_chat(messages: list[dict[str, str]]) -> str:
    """Send messages to the configured model adapter.

    Kept as a module-level function because existing callers and tests replace
    `engine.ollama_chat`. Removed in Sprint 9.
    """
    return get_model().chat(messages)


def select_memories(candidates: list[dict], budget_tokens: int) -> list[dict]:
    """Keep ranked candidates that fit the budget. Never truncates a memory."""
    return ame.select_within_budget(candidates, budget_tokens)[0]


def retrieval_query(query: str, working: WorkingMemory) -> str:
    """The text that will be searched for this message (see ame.analyze_task)."""
    return ame.analyze_task(query, working).retrieval_query


def answer(
    query: str,
    working: WorkingMemory | None = None,
    model: ChatModel | None = None,
) -> tuple[str, list[dict]]:
    """Answer a query using stored memories and (optionally) Working Memory.

    Without a WorkingMemory object the call is stateless, as in Sprint 1.
    Without a `model`, the configured adapter is used (via ollama_chat).
    """
    working = working if working is not None else WorkingMemory()
    prepared = ame.prepare(query, working)
    if model is None:
        response = ollama_chat(prepared.messages)
    else:
        response = model.chat(prepared.messages)
    # Only record usage and the turn after the model call succeeds.
    ame.finish(prepared, query, response, working)
    return response, prepared.memories