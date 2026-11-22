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

import pytest

from amco.summaries import check_summary, summary_limit


def test_default_settings_allow_512_tokens():
    assert summary_limit(4096, 512, 1024) == 512


def test_a_small_context_lowers_the_limit():
    # usable = 512, memories get half = 256, a summary gets half of that
    assert summary_limit(1024, 512, 1024) == 128


def test_a_small_memory_cap_lowers_the_limit():
    assert summary_limit(4096, 512, 100) == 50


def test_the_limit_never_drops_below_one():
    assert summary_limit(100, 200, 1024) == 1


def test_whitespace_is_collapsed():
    assert check_summary("  We chose\nSQLite \t today  ", 100) == "We chose SQLite today"


def test_an_empty_summary_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        check_summary("  \n ", 100)


def test_the_limit_is_inclusive():
    assert check_summary("x" * 40, 10) == "x" * 40  # exactly 10 tokens
    with pytest.raises(ValueError, match="too long"):
        check_summary("x" * 41, 10)  # 11 tokens