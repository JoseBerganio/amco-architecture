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

from amco.working import WorkingMemory, estimate_tokens


def _filled(turns: int = 3) -> WorkingMemory:
    wm = WorkingMemory()
    for _ in range(turns):
        wm.add("user", "u" * 40)       # 10 tokens each
        wm.add("assistant", "a" * 40)  # 10 tokens each
    return wm


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_messages_are_role_content_dicts():
    wm = WorkingMemory()
    wm.add("user", "hi")
    wm.add("assistant", "hello")
    assert wm.messages() == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_invalid_role_rejected():
    import pytest

    with pytest.raises(ValueError):
        WorkingMemory().add("system", "nope")


def test_trim_drops_oldest_whole_turns():
    wm = _filled(3)  # 6 turns, 60 tokens
    removed = wm.trim(25)
    assert removed == 4
    assert len(wm.turns) == 2
    assert wm.turns[0].role == "user"
    assert wm.dropped_turns == 4


def test_trim_leaves_history_starting_with_user_turn():
    wm = WorkingMemory()
    wm.add("user", "u" * 40)
    wm.add("assistant", "a" * 40)
    wm.add("user", "u" * 40)
    wm.add("assistant", "a" * 40)
    removed = wm.trim(35)  # dropping one turn leaves an assistant first, so it goes too
    assert removed == 2
    assert [t.role for t in wm.turns] == ["user", "assistant"]


def test_trim_does_nothing_when_history_fits():
    wm = _filled(2)
    assert wm.trim(1000) == 0
    assert len(wm.turns) == 4


def test_trim_with_zero_budget_empties_history():
    wm = _filled(2)
    wm.trim(0)
    assert wm.turns == []


def test_set_task_and_clear():
    wm = _filled(1)
    wm.set_task("  write the report  ")
    assert wm.task == "write the report"
    wm.set_task("   ")
    assert wm.task is None
    wm.set_task("again")
    wm.clear()
    assert wm.turns == [] and wm.task is None and wm.dropped_turns == 0