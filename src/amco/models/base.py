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

from __future__ import annotations

from typing import Protocol, runtime_checkable


class ModelError(RuntimeError):
    """Raised by a model adapter when a request cannot be completed.

    It subclasses RuntimeError so every existing `except RuntimeError` handler
    (and test) keeps working.
    """


@runtime_checkable
class ChatModel(Protocol):
    """The contract every model adapter follows."""

    @property
    def name(self) -> str: ...

    def chat(self, messages: list[dict[str, str]]) -> str: ...