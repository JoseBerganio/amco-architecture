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

"""Turn a SavedRun into JSON text and back. Pure: no files.

Only per-query results are stored. Summaries are recomputed on load, so a saved
file cannot disagree with itself. The `headline` block is for humans and is
ignored when reading.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .aggregate import build_suite_result
from .results import Observation, QueryResult, SuiteResult, ViewScores
from .run_record import RunError, RunMeta, SavedRun

FORMAT_VERSION = 1


# --- Writing -------------------------------------------------------------------


def _headline(suite: SuiteResult) -> dict[str, Any]:
    o = suite.overall
    return {
        "queries": o.queries,
        "candidate_hits": str(o.candidates.hits),
        "selected_hits": str(o.selected.hits),
        "candidate_mrr": None if o.candidates.mrr is None else round(o.candidates.mrr, 4),
        "false_inclusion": str(o.false_inclusion),
        "forbid_violations": str(o.forbid_violations),
    }


def run_to_payload(run: SavedRun) -> dict[str, Any]:
    suite = run.suite
    return {
        "format_version": FORMAT_VERSION,
        "meta": asdict(run.meta),
        "headline": _headline(suite),
        "suite": {
            "fixture_name": suite.fixture_name,
            "fixture_hash": suite.fixture_hash,
            "k": suite.k,
            "results": [asdict(r) for r in suite.results],
        },
    }


def dumps_run(run: SavedRun) -> str:
    """Pretty JSON ending in a single newline."""
    return json.dumps(run_to_payload(run), indent=2, ensure_ascii=False) + "\n"


# --- Reading -------------------------------------------------------------------


def _seq(value: Any, what: str) -> list | tuple:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{what} must be a list")
    return value


def _pairs(value: Any, what: str) -> tuple[tuple[str, str], ...]:
    return tuple((str(a), str(b)) for a, b in _seq(value, what))


def _observation_from(d: dict) -> Observation:
    return Observation(
        kind=d["kind"],
        wants_history=bool(d["wants_history"]),
        borrowed=bool(d["borrowed"]),
        depth=int(d["depth"]),
        search_text=d["search_text"],
        candidates=tuple(_seq(d["candidates"], "candidates")),
        selected=tuple(_seq(d["selected"], "selected")),
        skipped=_pairs(d["skipped"], "skipped"),
        conflicts=_pairs(d["conflicts"], "conflicts"),
        memory_tokens=int(d["memory_tokens"]),
        prompt_tokens=int(d["prompt_tokens"]),
        retrieval_ms=float(d["retrieval_ms"]),
        total_ms=float(d["total_ms"]),
    )


def _view_from(d: dict) -> ViewScores:
    return ViewScores(
        recall=d["recall"],
        hit=d["hit"],
        reciprocal_rank=d["reciprocal_rank"],
        precision=d["precision"],
    )


def _result_from(d: dict) -> QueryResult:
    return QueryResult(
        id=d["id"],
        query=d["query"],
        tags=tuple(_seq(d["tags"], "tags")),
        split=d["split"],
        expect=tuple(_seq(d["expect"], "expect")),
        forbid=tuple(_seq(d["forbid"], "forbid")),
        expect_kind=d["expect_kind"],
        observation=_observation_from(d["observation"]),
        candidates=_view_from(d["candidates"]),
        selected=_view_from(d["selected"]),
        forbidden_selected=tuple(_seq(d["forbidden_selected"], "forbidden_selected")),
        false_inclusion=d["false_inclusion"],
        kind_ok=d["kind_ok"],
        history_ok=bool(d["history_ok"]),
    )


def _meta_from(d: dict) -> RunMeta:
    return RunMeta(
        amco_version=d["amco_version"],
        python=d["python"],
        platform=d["platform"],
        sqlite_version=d["sqlite_version"],
        fts5=bool(d["fts5"]),
        mode=d["mode"],
        ranking_weights={str(k): float(v) for k, v in d["ranking_weights"].items()},
        half_life_days=float(d["half_life_days"]),
        context={str(k): int(v) for k, v in d["context"].items()},
        followup={str(k): int(v) for k, v in d["followup"].items()},
        retrieval={str(k): int(v) for k, v in d["retrieval"].items()},
        tags=tuple(_seq(d["tags"], "tags")),
        amco_variables=tuple(_seq(d["amco_variables"], "amco_variables")),
        created_at=d["created_at"],
        note=d.get("note"),
    )


def run_from_payload(data: Any) -> SavedRun:
    if not isinstance(data, dict):
        raise RunError("expected a JSON object")
    version = data.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise RunError(
            "missing or invalid 'format_version'; this does not look like an AMCO evaluation run"
        )
    if version > FORMAT_VERSION:
        raise RunError(
            f"run format version {version} is newer than this AMCO understands "
            f"({FORMAT_VERSION}); upgrade AMCO to read it"
        )
    if version < FORMAT_VERSION:
        raise RunError(f"unsupported run format version {version}")
    try:
        meta = _meta_from(data["meta"])
        suite = data["suite"]
        results = [_result_from(r) for r in _seq(suite["results"], "results")]
        built = build_suite_result(
            suite["fixture_name"], suite["fixture_hash"], int(suite["k"]), results
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RunError(f"malformed run data ({type(exc).__name__}: {exc})") from exc
    return SavedRun(meta, built)


def loads_run(text: str) -> SavedRun:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RunError(f"not valid JSON: {exc}") from exc
    return run_from_payload(data)