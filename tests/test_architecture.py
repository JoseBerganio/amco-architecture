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

"""Architecture: a module may import only from modules to its left in the layering."""

import ast
from pathlib import Path

import amco

ROOT = Path(amco.__file__).parent

# Lower rank = further left. A module may import only modules with a LOWER rank
# (imports within the same group, such as cli -> cli or models -> models, are fine).
RANKS = {
    "config": 0,
    "ranking": 1,
    "working": 1,
    "models": 1,
    "model": 2,  # temporary shim, removed in Sprint 9
    "storage.text": 2,
    "storage.db": 3,
    "storage.memories": 4,
    "storage.hygiene": 5,
    "storage.search": 6,
    "storage": 7,  # the package __init__ (public surface)
    "ame": 8,
    "lifecycle": 8,
    "engine": 9,
    "cli": 10,
}
TOP_LEVEL = {key.split(".")[0] for key in RANKS}


def _target_key(parts: list[str]) -> str | None:
    """Map an absolute module path such as ['amco', 'storage', 'db'] to a RANKS key."""
    if len(parts) < 2 or parts[0] != "amco" or parts[1] not in TOP_LEVEL:
        return None
    if parts[1] == "storage" and len(parts) > 2:
        return f"storage.{parts[2]}"
    return parts[1]


def _violations(key: str, package: list[str], source: str) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        targets: list[list[str]] = []
        if isinstance(node, ast.ImportFrom) and node.level:
            base = package[: len(package) - (node.level - 1)]
            if node.module:
                targets.append(base + node.module.split("."))
            else:
                targets.extend(base + [alias.name] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module.split("."))
        elif isinstance(node, ast.Import):
            targets.extend(alias.name.split(".") for alias in node.names)
        for parts in targets:
            target = _target_key(parts)
            if target is None or target == key:
                continue
            dotted = ".".join(parts)
            if RANKS[target] >= RANKS[key]:
                problems.append(f"imports {dotted}, which is not to its left in the layering")
            elif target.startswith("storage.") and not key.startswith("storage"):
                problems.append(f"imports {dotted}; code outside storage must use amco.storage")
    return problems


def _key_and_package(path: Path):
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    package = ["amco"] + parts[:-1]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return None  # amco/__init__.py
    if parts[0] == "storage":
        return ("storage" if len(parts) == 1 else f"storage.{parts[1]}"), package
    return parts[0], package


def test_every_module_respects_the_layering():
    problems: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        info = _key_and_package(path)
        if info is None:
            continue
        key, package = info
        assert key in RANKS, f"{path.relative_to(ROOT)} has no entry in RANKS; add one"
        for problem in _violations(key, package, path.read_text(encoding="utf-8")):
            problems.append(f"{path.relative_to(ROOT)}: {problem}")
    assert problems == []


def test_checker_rejects_an_upward_import():
    source = "from .search import search_memories\n"
    assert _violations("storage.db", ["amco", "storage"], source)


def test_checker_rejects_reaching_into_storage_submodules_from_outside():
    assert _violations("ame", ["amco"], "from .storage.db import connect\n")


def test_checker_accepts_legal_imports():
    source = "from .db import session\nfrom ..ranking import rank_memories\n"
    assert _violations("storage.search", ["amco", "storage"], source) == []