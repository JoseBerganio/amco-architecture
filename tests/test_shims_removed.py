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

"""The temporary shims from Sprints 6 to 8 must stay gone."""

import importlib
from pathlib import Path

import pytest

import amco
import amco.engine as engine
import amco.storage as storage
from amco.storage import db as db_module

ROOT = Path(amco.__file__).parent


def test_model_shim_module_is_gone():
    assert not (ROOT / "model.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amco.model")


def test_engine_no_longer_exposes_the_old_names():
    for name in ("ollama_chat", "context_settings"):
        assert not hasattr(engine, name), f"engine.{name} should be gone"


def test_storage_no_longer_exposes_the_fts_seam():
    assert not hasattr(storage, "_has_fts")
    assert not hasattr(db_module, "_fts_available")
    assert hasattr(db_module, "_has_fts")