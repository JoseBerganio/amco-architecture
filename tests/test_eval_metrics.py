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

import ast
from pathlib import Path

import pytest

import amco.evaluation.metrics as metrics_module
from amco.evaluation import (
    Ratio,
    describe,
    forbidden_hits,
    has_false_inclusion,
    is_hit,
    mean_defined,
    percentile,
    precision_at_k,
    ratio,
    recall_at_k,
    reciprocal_rank,
)


# --- Purity ------------------------------------------------------------------------


def test_metrics_module_imports_only_the_standard_library():
    tree = ast.parse(Path(metrics_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "metrics.py must not use relative imports"
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "math", "collections", "dataclasses"}


# --- recall / hit ----------------------------------------------------------------------


def test_recall_counts_only_the_top_k():
    ranked = ["x", "a", "y", "b"]
    assert recall_at_k(["a", "b"], ranked, 2) == pytest.approx(0.5)
    assert recall_at_k(["a", "b"], ranked, 4) == pytest.approx(1.0)
    assert recall_at_k(["a", "b"], ranked, 1) == pytest.approx(0.0)


def test_recall_is_none_when_nothing_is_expected():
    assert recall_at_k([], ["a"], 5) is None
    assert is_hit([], ["a"], 5) is None


def test_recall_with_k_larger_than_the_results():
    assert recall_at_k(["a"], ["a"], 50) == pytest.approx(1.0)
    assert recall_at_k(["a"], [], 5) == pytest.approx(0.0)


def test_repeated_keys_use_one_slot_and_count_once():
    assert recall_at_k(["a", "b"], ["a", "a", "b"], 2) == pytest.approx(1.0)
    assert recall_at_k(["a", "a"], ["a"], 1) == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [0, -1, True, 2.5])
def test_invalid_k_is_rejected(bad):
    with pytest.raises(ValueError):
        recall_at_k(["a"], ["a"], bad)


def test_is_hit_needs_every_expected_key():
    ranked = ["a", "x", "b"]
    assert is_hit(["a", "b"], ranked, 3) is True
    assert is_hit(["a", "b"], ranked, 2) is False
    assert is_hit(["a"], ranked, 1) is True


# --- reciprocal rank ---------------------------------------------------------------------


def test_reciprocal_rank_uses_the_first_expected_key():
    assert reciprocal_rank(["a"], ["x", "y", "a"]) == pytest.approx(1 / 3)
    assert reciprocal_rank(["b", "a"], ["x", "a", "b"]) == pytest.approx(0.5)


def test_reciprocal_rank_missing_cut_off_and_undefined():
    assert reciprocal_rank(["a"], ["x", "y"]) == 0.0
    assert reciprocal_rank(["a"], ["x", "y", "a"], k=2) == 0.0
    assert reciprocal_rank([], ["a"]) is None


def test_reciprocal_rank_ignores_repeats_when_ranking():
    assert reciprocal_rank(["a"], ["x", "x", "a"]) == pytest.approx(0.5)


# --- precision --------------------------------------------------------------------------------


def test_precision_divides_by_what_was_returned():
    assert precision_at_k(["a", "b"], ["a", "x", "b", "y"], 4) == pytest.approx(0.5)
    assert precision_at_k(["a", "b"], ["a", "x", "b", "y"], 2) == pytest.approx(0.5)
    assert precision_at_k(["a"], ["a"], 5) == pytest.approx(1.0)  # one result, and it was right


def test_precision_is_none_without_expectations_or_results():
    assert precision_at_k([], ["a"], 5) is None
    assert precision_at_k(["a"], [], 5) is None


# --- selected-memory checks ----------------------------------------------------------------------


def test_forbidden_hits_lists_each_banned_key_once_in_order():
    assert forbidden_hits(["x", "y"], ["y", "a", "y", "x"]) == ["y", "x"]
    assert forbidden_hits([], ["a"]) == []
    assert forbidden_hits(["x"], []) == []


def test_false_inclusion_means_anything_selected():
    assert has_false_inclusion(["a"]) is True
    assert has_false_inclusion([]) is False


# --- aggregation ---------------------------------------------------------------------------------


def test_ratio_keeps_raw_counts_and_skips_undefined():
    r = ratio([True, False, None, True])
    assert r == Ratio(2, 3)
    assert str(r) == "2/3 (66.7%)"
    assert r.value == pytest.approx(2 / 3)


def test_ratio_formats_the_planned_example_and_the_empty_case():
    assert str(Ratio(37, 47)) == "37/47 (78.7%)"
    empty = ratio([None, None])
    assert str(empty) == "0/0 (n/a)" and empty.value is None


def test_mean_defined_skips_none():
    assert mean_defined([1, None, 3]) == pytest.approx(2.0)
    assert mean_defined([None]) is None
    assert mean_defined([]) is None


def test_percentile_interpolates_linearly():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([4, 1, 3, 2], 95) == pytest.approx(3.85)  # order does not matter
    assert percentile([1, 2, 3, 4], 0) == pytest.approx(1.0)
    assert percentile([1, 2, 3, 4], 100) == pytest.approx(4.0)
    assert percentile([7], 95) == pytest.approx(7.0)


def test_percentile_edge_cases():
    assert percentile([], 50) is None
    with pytest.raises(ValueError):
        percentile([1], 101)
    with pytest.raises(ValueError):
        percentile([1], -1)


def test_describe_summarises_a_series_and_handles_empty():
    d = describe([1, 2, 3, 4, None])
    assert d.count == 4
    assert d.mean == pytest.approx(2.5)
    assert d.p50 == pytest.approx(2.5)
    assert d.p95 == pytest.approx(3.85)
    assert d.maximum == pytest.approx(4.0)
    empty = describe([None])
    assert empty.count == 0 and empty.mean is None and empty.maximum is None