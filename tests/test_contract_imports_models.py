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

"""Contract: the Sprint 7 public names (and the ones that moved) stay importable."""

import importlib

import pytest

SURFACE = {
    "amco.models": ["ChatModel", "ModelError", "OllamaChat", "PROVIDERS", "get_model"],
    "amco.models.base": ["ChatModel", "ModelError"],
    "amco.models.ollama": ["OllamaChat"],
    "amco.config": [
        "DEFAULT_DB", "DEFAULT_PROVIDER", "DEFAULT_WEIGHT_RELEVANCE",
        "DEFAULT_WEIGHT_CONFIDENCE", "DEFAULT_WEIGHT_FRESHNESS",
        "DEFAULT_WEIGHT_USEFULNESS", "database_path", "provider_name",
        "timeout_seconds", "ranking_weight_settings",
    ],
    "amco.storage": ["DEFAULT_DB", "database_path"],
    "amco.ranking": ["weights_from_env", "RankingWeights"],
    "amco.engine": ["get_model", "ChatModel"],
}

CASES = [(module, name) for module, names in SURFACE.items() for name in names]


@pytest.mark.parametrize("module, name", CASES)
def test_name_is_importable(module, name):
    assert hasattr(importlib.import_module(module), name), f"{module}.{name} is missing"