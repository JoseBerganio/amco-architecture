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

"""Contract: the CLI command tree must not change during the 0.5.0 refactor.

The tree is compared structurally (names, order, options, defaults, help text),
not as rendered help, so terminal width and Rich versions do not matter.
It reads the command objects by attribute only, so it works whether or not the
installed Typer depends on a separate `click` package.

Regenerate the snapshot ONLY from v0.2.0 code:  python tests/test_contract_cli.py
"""

import json
from pathlib import Path

import typer

from amco.cli import app

SNAPSHOT = Path(__file__).parent / "snapshots" / "cli_structure.json"


def _plain(value):
    """Keep JSON-friendly values; collapse sentinels and callables to None."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _param(param) -> dict:
    return {
        "kind": param.param_type_name,
        "name": param.name,
        "opts": list(param.opts),
        "secondary_opts": list(param.secondary_opts),
        "required": bool(param.required),
        "default": _plain(param.default),
        "type": param.type.name,
        "min": _plain(getattr(param.type, "min", None)),
        "max": _plain(getattr(param.type, "max", None)),
        "is_flag": bool(getattr(param, "is_flag", False)),
        "help": getattr(param, "help", None),
    }


def _command(cmd, name: str | None = None) -> dict:
    info = {
        "name": name or cmd.name,
        "help": cmd.help,
        "params": [_param(p) for p in cmd.params],
    }
    if hasattr(cmd, "commands"):  # a command group
        info["no_args_is_help"] = bool(cmd.no_args_is_help)
        info["commands"] = [_command(c) for c in cmd.commands.values()]
    return info


def snapshot() -> dict:
    root = typer.main.get_command(app)
    return json.loads(json.dumps(_command(root, "amco")))


def test_cli_structure_matches_v020_snapshot():
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot() == expected


def test_command_names_and_order_are_stable():
    tree = snapshot()
    assert [c["name"] for c in tree["commands"]] == ["version", "init", "chat", "memory"]
    memory = next(c for c in tree["commands"] if c["name"] == "memory")
    assert [c["name"] for c in memory["commands"]] == [
        "add", "list", "inspect", "update", "supersede",
        "restore", "review", "search", "reindex", "delete",
    ]


if __name__ == "__main__":
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps(snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {SNAPSHOT}")