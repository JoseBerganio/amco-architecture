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

"""Turn raw JSON data into a validated FixtureSet.

Pure functions: no files, no database. Problems are collected and reported
together so a fixture author can fix them in one pass.
"""

from __future__ import annotations

import re
from typing import Any

from ..storage import VALID_KINDS, VALID_TYPES
from .fixture_types import (
    KNOWN_TAGS,
    TASK_KINDS,
    VALID_ROLES,
    VALID_SPLITS,
    FixtureError,
    FixtureMemory,
    FixtureQuery,
    FixtureSet,
    FixtureTurn,
)

_MISSING = object()
_KEY_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")

_TOP_FIELDS = {"name", "description", "memories", "queries"}
_MEMORY_FIELDS = {
    "key", "content", "category", "memory_type", "confidence",
    "age_days", "expires_in_days", "supersedes", "use_count",
    "kind", "period_age_days",
}
_QUERY_FIELDS = {
    "id", "query", "expect", "forbid", "history", "turns",
    "task", "tags", "expect_kind", "split",
}
_TURN_FIELDS = {"role", "content"}


# --- Field readers (each raises FixtureError with its location) ---


def _object(raw: Any, where: str, allowed: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise FixtureError(f"{where}: expected an object")
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise FixtureError(f"{where}: unknown field(s): {', '.join(unknown)}")
    return raw


def _text(raw: dict, name: str, where: str, default: Any = _MISSING) -> Any:
    """Non-empty text. A missing or null field returns `default`, or fails if there is none."""
    if raw.get(name) is None:
        if default is _MISSING:
            raise FixtureError(f"{where}: missing required field '{name}'")
        return default
    value = raw[name]
    if not isinstance(value, str):
        raise FixtureError(f"{where}: '{name}' must be text")
    value = value.strip()
    if not value:
        raise FixtureError(f"{where}: '{name}' cannot be empty")
    return value


def _choice(raw: dict, name: str, where: str, allowed: tuple[str, ...], default: Any) -> Any:
    value = _text(raw, name, where, default)
    if value is not None and value not in allowed:
        raise FixtureError(f"{where}: '{name}' must be one of {', '.join(allowed)}")
    return value


def _whole(raw: dict, name: str, where: str, default: Any, minimum: int | None = None) -> Any:
    if raw.get(name) is None:
        return default
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureError(f"{where}: '{name}' must be a whole number")
    if minimum is not None and value < minimum:
        raise FixtureError(f"{where}: '{name}' must be at least {minimum}")
    return value


def _fraction(raw: dict, name: str, where: str, default: float) -> float:
    if raw.get(name) is None:
        return default
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise FixtureError(f"{where}: '{name}' must be a number from 0 to 1")
    return float(value)


def _flag(raw: dict, name: str, where: str, default: bool) -> bool:
    if raw.get(name) is None:
        return default
    if not isinstance(raw[name], bool):
        raise FixtureError(f"{where}: '{name}' must be true or false")
    return raw[name]


def _words(raw: dict, name: str, where: str) -> tuple[str, ...]:
    """A list of distinct, non-empty strings. Missing or null means an empty list."""
    items = raw.get(name)
    if items is None:
        return ()
    if not isinstance(items, list):
        raise FixtureError(f"{where}: '{name}' must be a list")
    out: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise FixtureError(f"{where}: '{name}' must contain non-empty text only")
        item = item.strip()
        if item in out:
            raise FixtureError(f"{where}: '{name}' lists '{item}' twice")
        out.append(item)
    return tuple(out)


# --- Items -------------------------------------------------------------------


def parse_memory(raw: Any, where: str) -> FixtureMemory:
    raw = _object(raw, where, _MEMORY_FIELDS)
    key = _text(raw, "key", where)
    if not _KEY_RE.fullmatch(key):
        raise FixtureError(
            f"{where}: key must use lowercase letters, digits, '-' or '_' "
            f"and start with a letter or digit"
        )
    where = f"{where} (key '{key}')"
    return FixtureMemory(
        key=key,
        content=_text(raw, "content", where),
        category=_text(raw, "category", where, "general"),
        memory_type=_choice(raw, "memory_type", where, tuple(VALID_TYPES), "persistent"),
        confidence=_fraction(raw, "confidence", where, 1.0),
        age_days=_whole(raw, "age_days", where, 0, minimum=0),
        expires_in_days=_whole(raw, "expires_in_days", where, None),
        supersedes=_text(raw, "supersedes", where, None),
        use_count=_whole(raw, "use_count", where, 0, minimum=0),
        kind=_choice(raw, "kind", where, tuple(VALID_KINDS), "fact"),
        period_age_days=_whole(raw, "period_age_days", where, None, minimum=0),
    )


def _parse_turns(raw: dict, where: str) -> tuple[FixtureTurn, ...]:
    items = raw.get("turns")
    if items is None:
        return ()
    if not isinstance(items, list):
        raise FixtureError(f"{where}: 'turns' must be a list")
    turns = []
    for i, item in enumerate(items):
        spot = f"{where}: turns[{i}]"
        item = _object(item, spot, _TURN_FIELDS)
        turns.append(
            FixtureTurn(
                role=_choice(item, "role", spot, VALID_ROLES, _MISSING),
                content=_text(item, "content", spot),
            )
        )
    if turns and turns[0].role != "user":
        raise FixtureError(
            f"{where}: 'turns' must start with a user turn "
            f"(Working Memory drops a leading assistant turn)"
        )
    return tuple(turns)


def parse_query(raw: Any, where: str) -> FixtureQuery:
    raw = _object(raw, where, _QUERY_FIELDS)
    query_id = _text(raw, "id", where)
    where = f"{where} (id '{query_id}')"
    tags = _words(raw, "tags", where)
    if not tags:
        raise FixtureError(f"{where}: 'tags' must list at least one tag")
    unknown = sorted(set(tags) - KNOWN_TAGS)
    if unknown:
        raise FixtureError(
            f"{where}: unknown tag(s): {', '.join(unknown)}. "
            f"Known tags: {', '.join(sorted(KNOWN_TAGS))}"
        )
    return FixtureQuery(
        id=query_id,
        query=_text(raw, "query", where),
        expect=_words(raw, "expect", where),
        forbid=_words(raw, "forbid", where),
        history=_flag(raw, "history", where, False),
        turns=_parse_turns(raw, where),
        task=_text(raw, "task", where, None),
        tags=tags,
        expect_kind=_choice(raw, "expect_kind", where, TASK_KINDS, None),
        split=_choice(raw, "split", where, VALID_SPLITS, None),
    )


# --- Rules that need the whole set ---------------------------------------------


def _check_memories(memories: list[FixtureMemory]) -> tuple[list[str], dict[str, int], set[str]]:
    """Returns (problems, key -> position, keys that can never be retrieved)."""
    problems: list[str] = []
    index: dict[str, int] = {}
    for i, m in enumerate(memories):
        if m.key in index:
            problems.append(
                f"memories[{i}]: duplicate key '{m.key}' (first used at memories[{index[m.key]}])"
            )
        else:
            index[m.key] = i

    superseded: set[str] = set()
    for i, m in enumerate(memories):
        if m.supersedes is None:
            continue
        where = f"memories[{i}] (key '{m.key}')"
        if m.supersedes == m.key:
            problems.append(f"{where}: cannot supersede itself")
        elif m.supersedes not in index:
            problems.append(f"{where}: supersedes unknown memory '{m.supersedes}'")
        elif index[m.supersedes] > i:
            problems.append(
                f"{where}: supersedes '{m.supersedes}', which is defined later; "
                f"define the older memory first"
            )
        elif m.supersedes in superseded:
            problems.append(f"{where}: '{m.supersedes}' is already superseded by another memory")
        else:
            superseded.add(m.supersedes)

    expired = {m.key for m in memories if m.expires_in_days is not None and m.expires_in_days < 0}
    return problems, index, superseded | expired


def _check_queries(
    queries: list[FixtureQuery], index: dict[str, int], inactive: set[str]
) -> list[str]:
    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, q in enumerate(queries):
        where = f"queries[{i}] (id '{q.id}')"
        if q.id in seen:
            problems.append(f"queries[{i}]: duplicate id '{q.id}' (first used at queries[{seen[q.id]}])")
        else:
            seen[q.id] = i
        for field, keys in (("expect", q.expect), ("forbid", q.forbid)):
            for key in keys:
                if key not in index:
                    problems.append(f"{where}: {field} names unknown memory '{key}'")
        both = sorted(set(q.expect) & set(q.forbid))
        if both:
            problems.append(f"{where}: {', '.join(both)} is in both expect and forbid")
        for key in q.expect:
            if key in inactive:
                problems.append(
                    f"{where}: expects '{key}', which is superseded or expired and can never be retrieved"
                )
        tags = set(q.tags)
        if "negative" in tags and q.expect:
            problems.append(f"{where}: tagged 'negative' but expects memories")
        if ("chitchat" in tags or q.expect_kind == "chitchat") and q.expect:
            problems.append(f"{where}: a chitchat query cannot expect memories")
        if not q.expect and not q.forbid and not tags & {"negative", "chitchat"}:
            problems.append(
                f"{where}: expects nothing; tag it 'negative' or 'chitchat', or give 'forbid'"
            )
    return problems


# --- Entry point -------------------------------------------------------------


def _report(problems: list[str]) -> str:
    return f"{len(problems)} problem(s) in the fixtures:\n" + "\n".join(f"  - {p}" for p in problems)


def _list(top: dict, name: str) -> list:
    items = top.get(name)
    if not isinstance(items, list) or not items:
        raise FixtureError(f"fixtures: '{name}' must be a non-empty list")
    return items


def parse_fixtures(data: Any) -> FixtureSet:
    """Validate raw JSON data. Raises FixtureError listing every problem found."""
    top = _object(data, "fixtures", _TOP_FIELDS)
    name = _text(top, "name", "fixtures")
    description = _text(top, "description", "fixtures", "")

    problems: list[str] = []
    memories: list[FixtureMemory] = []
    queries: list[FixtureQuery] = []
    for i, raw in enumerate(_list(top, "memories")):
        try:
            memories.append(parse_memory(raw, f"memories[{i}]"))
        except FixtureError as exc:
            problems.append(str(exc))
    for i, raw in enumerate(_list(top, "queries")):
        try:
            queries.append(parse_query(raw, f"queries[{i}]"))
        except FixtureError as exc:
            problems.append(str(exc))
    if problems:
        raise FixtureError(_report(problems))

    problems, index, inactive = _check_memories(memories)
    problems += _check_queries(queries, index, inactive)
    if problems:
        raise FixtureError(_report(problems))
    return FixtureSet(name, description, tuple(memories), tuple(queries))