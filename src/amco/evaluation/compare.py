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

"""Compare two saved runs. Pure: no files, no Rich."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .metrics import Ratio
from .results import QueryResult, Summary
from .run_record import RunError, SavedRun

MAX_NET_LOSS = 1  # the 10a ship rule: at most 1 net query lost
_EPS = 1e-9


# --- Result types -------------------------------------------------------------


@dataclass(frozen=True)
class MetricDelta:
    label: str
    before: str                 # already formatted; ratios keep their raw counts
    after: str
    delta: float | None         # after - before; None when either side is undefined
    direction: str              # "higher" or "lower" is better, or "info" (no judgement)
    unit: str                   # "ratio" | "score" | "tokens" | "ms"

    @property
    def verdict(self) -> str:
        if self.delta is None:
            return "n/a"
        if abs(self.delta) < _EPS:
            return "same"
        if self.direction == "info":
            return "changed"
        improved = self.delta > 0 if self.direction == "higher" else self.delta < 0
        return "better" if improved else "worse"


@dataclass(frozen=True)
class Flip:
    """One query whose status changed. `before` and `after` are True when the status is good."""

    id: str
    query: str
    view: str                   # "candidates" | "selected" | "forbid" | "noise"
    before: bool
    after: bool
    split: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SettingDiff:
    field: str
    before: str
    after: str


@dataclass(frozen=True)
class Comparison:
    a_label: str
    b_label: str
    same_fixtures: bool
    queries_compared: int
    metrics: tuple[MetricDelta, ...]
    flips: tuple[Flip, ...]
    only_in_a: tuple[str, ...]
    only_in_b: tuple[str, ...]
    settings: tuple[SettingDiff, ...]

    def count(self, view: str, *, gained: bool) -> int:
        """Queries that became good (gained) or stopped being good (lost) in a view."""
        return sum(1 for f in self.flips if f.view == view and f.after == gained)

    def net(self, view: str) -> int:
        return self.count(view, gained=True) - self.count(view, gained=False)

    @property
    def ship_rule_ok(self) -> bool | None:
        """True if no more than MAX_NET_LOSS queries were lost net, in both hit views.

        None when the fixtures differ, because then the rule is not meaningful.
        """
        if not self.same_fixtures:
            return None
        return all(self.net(view) >= -MAX_NET_LOSS for view in ("candidates", "selected"))


# --- Metric table ---------------------------------------------------------------


@dataclass(frozen=True)
class _Spec:
    label: str
    get: Callable[[Summary], Ratio | float | None]
    direction: str
    unit: str


_SPECS = (
    _Spec("Candidate hits", lambda s: s.candidates.hits, "higher", "ratio"),
    _Spec("Candidate recall", lambda s: s.candidates.recall, "higher", "score"),
    _Spec("Candidate MRR", lambda s: s.candidates.mrr, "higher", "score"),
    _Spec("Candidate precision", lambda s: s.candidates.precision, "higher", "score"),
    _Spec("Selected hits", lambda s: s.selected.hits, "higher", "ratio"),
    _Spec("Selected recall", lambda s: s.selected.recall, "higher", "score"),
    _Spec("Selected MRR", lambda s: s.selected.mrr, "higher", "score"),
    _Spec("Selected precision", lambda s: s.selected.precision, "higher", "score"),
    _Spec("Forbidden memories selected", lambda s: s.forbid_violations, "lower", "ratio"),
    _Spec("False inclusion", lambda s: s.false_inclusion, "lower", "ratio"),
    _Spec("Classifier matches label", lambda s: s.classifier, "higher", "ratio"),
    _Spec("Memory tokens (mean)", lambda s: s.memory_tokens.mean, "info", "tokens"),
    _Spec("Prompt tokens (mean)", lambda s: s.prompt_tokens.mean, "info", "tokens"),
    _Spec("Retrieval ms (p50)", lambda s: s.retrieval_ms.p50, "info", "ms"),
    _Spec("Retrieval ms (p95)", lambda s: s.retrieval_ms.p95, "info", "ms"),
    _Spec("Total ms (p95)", lambda s: s.total_ms.p95, "info", "ms"),
)


def _value(x: Ratio | float | None) -> float | None:
    return x.value if isinstance(x, Ratio) else x


def _show(x: Ratio | float | None, unit: str) -> str:
    if isinstance(x, Ratio):
        return str(x)
    if x is None:
        return "n/a"
    return f"{x:.3f}" if unit == "score" else f"{x:.1f}"


def _metric_deltas(a: Summary, b: Summary) -> tuple[MetricDelta, ...]:
    rows = []
    for spec in _SPECS:
        before, after = spec.get(a), spec.get(b)
        bv, av = _value(before), _value(after)
        rows.append(
            MetricDelta(
                label=spec.label,
                before=_show(before, spec.unit),
                after=_show(after, spec.unit),
                delta=None if bv is None or av is None else av - bv,
                direction=spec.direction,
                unit=spec.unit,
            )
        )
    return tuple(rows)


# --- Per-query status ------------------------------------------------------------

_VIEWS: tuple[tuple[str, Callable[[QueryResult], bool | None]], ...] = (
    ("candidates", lambda r: r.candidates.hit),
    ("selected", lambda r: r.selected.hit),
    ("forbid", lambda r: None if not r.forbid else not r.forbidden_selected),
    ("noise", lambda r: None if r.false_inclusion is None else not r.false_inclusion),
)


# --- Settings ----------------------------------------------------------------------

_SETTING_FIELDS = (
    "amco_version", "python", "platform", "sqlite_version", "fts5", "mode",
    "ranking_weights", "half_life_days", "context", "followup", "retrieval",
    "tags", "amco_variables",
)


def _show_setting(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items()) or "(none)"
    if isinstance(value, (tuple, list)):
        return ", ".join(str(v) for v in value) or "(none)"
    return str(value)


def _setting_diffs(a: SavedRun, b: SavedRun) -> tuple[SettingDiff, ...]:
    diffs = []
    if a.suite.k != b.suite.k:
        diffs.append(SettingDiff("k", str(a.suite.k), str(b.suite.k)))
    for name in _SETTING_FIELDS:
        before, after = getattr(a.meta, name), getattr(b.meta, name)
        if before != after:
            diffs.append(SettingDiff(name, _show_setting(before), _show_setting(after)))
    return tuple(diffs)


# --- Entry point -------------------------------------------------------------------


def compare_runs(
    a: SavedRun,
    b: SavedRun,
    a_label: str = "A",
    b_label: str = "B",
    force: bool = False,
) -> Comparison:
    """Compare run `a` (before) with run `b` (after).

    Runs made on different fixtures are refused unless `force` is set. With force,
    only queries with the same id are matched, and the ship rule is not judged.
    """
    same = a.suite.fixture_hash == b.suite.fixture_hash
    if not same and not force:
        raise RunError(
            "These runs used different fixtures "
            f"({a.suite.fixture_hash[:12]} vs {b.suite.fixture_hash[:12]}), so their numbers "
            "are not comparable. Compare with force to match queries by id anyway."
        )
    a_by = {r.id: r for r in a.suite.results}
    b_by = {r.id: r for r in b.suite.results}
    shared = [r.id for r in b.suite.results if r.id in a_by]

    flips: list[Flip] = []
    for view, status in _VIEWS:
        for query_id in shared:
            before, after = status(a_by[query_id]), status(b_by[query_id])
            if before is None or after is None or before == after:
                continue
            after_result = b_by[query_id]
            flips.append(
                Flip(
                    id=query_id,
                    query=after_result.query,
                    view=view,
                    before=before,
                    after=after,
                    split=after_result.split,
                    tags=after_result.tags,
                )
            )

    return Comparison(
        a_label=a_label,
        b_label=b_label,
        same_fixtures=same,
        queries_compared=len(shared),
        metrics=_metric_deltas(a.suite.overall, b.suite.overall),
        flips=tuple(flips),
        only_in_a=tuple(r.id for r in a.suite.results if r.id not in b_by),
        only_in_b=tuple(r.id for r in b.suite.results if r.id not in a_by),
        settings=_setting_diffs(a, b),
    )