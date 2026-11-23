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

"""Load fixture files (packaged default or a path) and fingerprint them."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from .fixture_parse import parse_fixtures
from .fixture_types import FixtureError, FixtureSet

DEFAULT_DATASET = "default.json"


def _read(path: Path | None) -> tuple[str, str]:
    """Return (text, label). utf-8-sig tolerates the BOM some Windows editors add."""
    if path is None:
        label = f"packaged dataset '{DEFAULT_DATASET}'"
        resource = files("amco.evaluation").joinpath("datasets", DEFAULT_DATASET)
        reader = lambda: resource.read_text(encoding="utf-8-sig")  # noqa: E731
    else:
        label = f"fixtures file {path}"
        reader = lambda: Path(path).read_text(encoding="utf-8-sig")  # noqa: E731
    try:
        return reader(), label
    except OSError as exc:
        raise FixtureError(f"Cannot read {label}: {exc}") from exc


def load_fixtures(path: Path | str | None = None) -> FixtureSet:
    """Load and validate fixtures. With no path, the packaged default dataset is used."""
    text, label = _read(Path(path) if path is not None else None)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FixtureError(f"{label} is not valid JSON: {exc}") from exc
    try:
        return parse_fixtures(data)
    except FixtureError as exc:
        raise FixtureError(f"{label}: {exc}") from exc


# Optional fields added after the 0.6 freeze are left out of the canonical form while they
# hold their default, so giving FixtureMemory a new field never changes the hash of a
# dataset that does not use it (and so never invalidates an existing baseline).
_OMIT_AT_DEFAULT = {"kind": "fact", "period_age_days": None}


def _memory_payload(memory) -> dict:
    data = asdict(memory)
    for name, default in _OMIT_AT_DEFAULT.items():
        if data.get(name) == default:
            del data[name]
    return data


def canonical_json(fixtures: FixtureSet) -> str:
    """Stable text form of what affects results: memories and queries only.

    Name and description are left out on purpose, so editing prose never
    invalidates saved runs.
    """
    payload = {
        "memories": [_memory_payload(m) for m in fixtures.memories],
        "queries": [asdict(q) for q in fixtures.queries],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fixture_hash(fixtures: FixtureSet) -> str:
    return hashlib.sha256(canonical_json(fixtures).encode("utf-8")).hexdigest()