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

"""Rich renderings of runs, comparisons and run lists.

Builders return Rich renderables and never print, so tests can render them to a string.
Every cell is a Text object, so query text such as "[bold]" is shown literally.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from rich.console import Group
from rich.table import Table
from rich.text import Text

from .compare import Comparison, MetricDelta
from .metrics import Distribution, Ratio
from .results import QueryResult, SuiteResult, Summary
from .run_record import SavedRun
from .store import RunListing


# --- Small helpers ---------------------------------------------------------------


def _score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _one(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _counts(r: Ratio) -> str:
    return f"{r.num}/{r.den}"


def _table(
    title: str,
    columns: Sequence[str],
    right: Iterable[str] = (),
    caption: str | None = None,
) -> Table:
    table = Table(
        title=Text(title, style="bold"),
        title_justify="left",
        caption=Text(caption, style="dim") if caption else None,
        caption_justify="left",
    )
    right = set(right)
    for column in columns:
        table.add_column(column, justify="right" if column in right else "left")
    return table


def _row(table: Table, *cells: object) -> None:
    table.add_row(*(c if isinstance(c, Text) else Text(str(c)) for c in cells))


# --- One run ---------------------------------------------------------------------


def _header(run: SavedRun, name: str | None) -> list[Text]:
    m, s = run.meta, run.suite
    filtered = f", tags: {', '.join(m.tags)}" if m.tags else ""
    lines = [
        Text(f"Run: {name or '(unsaved)'}", style="bold"),
        Text(
            f"Fixtures: {s.fixture_name} (hash {s.fixture_hash[:12]}), "
            f"{s.overall.queries} queries, k={s.k}, mode={m.mode}{filtered}"
        ),
        Text(
            f"AMCO {m.amco_version}, Python {m.python}, SQLite {m.sqlite_version} "
            f"(FTS5: {'yes' if m.fts5 else 'NO'}), made {m.created_at}"
        ),
    ]
    if m.note:
        lines.append(Text(f"Note: {m.note}"))
    if m.amco_variables:
        lines.append(
            Text("AMCO_* settings were set: " + ", ".join(m.amco_variables), style="yellow")
        )
    if not m.fts5:
        lines.append(
            Text(
                "FTS5 was unavailable: these numbers come from the keyword fallback and are "
                "not comparable with FTS5 runs.",
                style="red",
            )
        )
    return lines


def _retrieval_table(s: Summary, k: int) -> Table:
    table = _table(
        f"Retrieval (k={k})",
        ["View", "Hits", "Recall", "MRR", "Precision"],
        right={"Hits", "Recall", "MRR", "Precision"},
        caption=(
            "Hits = every expected memory found. Candidates are judged in the top k of the "
            "pool the AME fetched (depth + 3, before duplicate removal); selected memories "
            "are judged whole. Precision averages only queries that returned something, "
            "so read it together with Hits."
        ),
    )
    for label, view in (("Candidates (top k)", s.candidates), ("Selected (prompt)", s.selected)):
        _row(table, label, view.hits, _score(view.recall), _score(view.mrr), _score(view.precision))
    return table


def _noise_table(s: Summary) -> Table:
    table = _table("Noise and labels", ["Check", "Result", "Better"], right={"Result"})
    _row(table, "Forbidden memories selected", s.forbid_violations, "lower")
    _row(table, "Selected when nothing expected", s.false_inclusion, "lower")
    _row(table, "Classifier matches label", s.classifier, "higher")
    _row(table, "History cues match label", s.history_labels, "higher")
    return table


def _cost_table(s: Summary) -> Table:
    table = _table(
        "Cost",
        ["Metric", "Mean", "p50", "p95", "Max"],
        right={"Mean", "p50", "p95", "Max"},
        caption="Timings vary from run to run; compare them loosely.",
    )
    series: Sequence[tuple[str, Distribution]] = (
        ("Memory tokens", s.memory_tokens),
        ("Prompt tokens", s.prompt_tokens),
        ("Retrieval ms", s.retrieval_ms),
        ("Total ms", s.total_ms),
    )
    for label, d in series:
        _row(table, label, _one(d.mean), _one(d.p50), _one(d.p95), _one(d.maximum))
    return table


def _group_table(title: str, groups: Mapping[str, Summary]) -> Table | None:
    if not groups:
        return None
    table = _table(
        title,
        ["Group", "Queries", "Cand hits", "Cand MRR", "Sel hits", "Sel precision",
         "False incl.", "Forbid viol."],
        right={"Queries", "Cand hits", "Cand MRR", "Sel hits", "Sel precision",
               "False incl.", "Forbid viol."},
        caption="Counts are queries. A query with several tags appears under each tag.",
    )
    for name, s in groups.items():
        _row(
            table, name, s.queries, _counts(s.candidates.hits), _score(s.candidates.mrr),
            _counts(s.selected.hits), _score(s.selected.precision),
            _counts(s.false_inclusion), _counts(s.forbid_violations),
        )
    return table


# --- Queries needing attention (--verbose) ---------------------------------------------


def _ranked(keys: Sequence[str]) -> str:
    return ", ".join(f"{i}. {key}" for i, key in enumerate(keys, start=1)) or "(none)"


def query_problems(r: QueryResult, k: int) -> list[str]:
    """Plain-language reasons a query needs attention. Empty means it is fine."""
    o = r.observation
    out: list[str] = []
    if r.expect:
        top = list(dict.fromkeys(o.candidates))[:k]
        if r.candidates.hit is False:
            found = sum(key in top for key in r.expect)
            out.append(f"candidates: found {found} of {len(r.expect)} expected in the top {k}")
        if r.selected.hit is False:
            found = sum(key in o.selected for key in r.expect)
            out.append(f"prompt: contains {found} of {len(r.expect)} expected")
    if r.forbidden_selected:
        out.append("prompt: contains forbidden " + ", ".join(r.forbidden_selected))
    if r.false_inclusion:
        out.append(f"prompt: {len(o.selected)} memories selected but none expected")
    if r.kind_ok is False:
        out.append(f"classifier: said '{o.kind}', label says '{r.expect_kind}'")
    if not r.history_ok:
        detected = "yes" if o.wants_history else "no"
        label = "no" if o.wants_history else "yes"
        out.append(f"history cues: detected {detected}, label says {label}")
    return out


def render_problems(suite: SuiteResult) -> Group:
    flagged = [(r, query_problems(r, suite.k)) for r in suite.results]
    flagged = [(r, problems) for r, problems in flagged if problems]
    parts: list[Text] = [
        Text(f"Queries needing attention: {len(flagged)} of {len(suite.results)}", style="bold")
    ]
    if not flagged:
        parts.append(Text("None."))
    for r, problems in flagged:
        o = r.observation
        parts.append(Text(f"\n{r.id}  {r.query}", style="bold"))
        parts.extend(Text(f"  - {p}") for p in problems)
        parts.append(Text(f"  expected:   {', '.join(r.expect) or '(nothing)'}"))
        parts.append(Text(f"  candidates: {_ranked(o.candidates[: suite.k])}"))
        parts.append(Text(f"  selected:   {_ranked(o.selected)}"))
        if o.borrowed:
            parts.append(Text(f"  search:     {o.search_text}"))
        if o.skipped:
            parts.append(Text("  skipped:    " + ", ".join(f"{k} ({why})" for k, why in o.skipped)))
    return Group(*parts)


def render_run(run: SavedRun, *, name: str | None = None, verbose: bool = False) -> Group:
    suite = run.suite
    parts: list = [*_header(run, name), Text("")]
    parts += [_retrieval_table(suite.overall, suite.k), _noise_table(suite.overall),
              _cost_table(suite.overall)]
    for table in (_group_table("By tag", suite.by_tag), _group_table("By split", suite.by_split)):
        if table is not None:
            parts.append(table)
    if verbose:
        parts += [Text(""), render_problems(suite)]
    return Group(*parts)


# --- Comparison ---------------------------------------------------------------------


def _change(m: MetricDelta) -> str:
    if m.delta is None:
        return "n/a"
    if abs(m.delta) < 1e-9:
        return "0"
    if m.unit == "ratio":
        return f"{m.delta * 100:+.1f} pts"
    if m.unit == "score":
        return f"{m.delta:+.3f}"
    return f"{m.delta:+.1f}"


_VERDICT_STYLE = {"better": "green", "worse": "red"}
_STATES = {
    "candidates": ("miss", "hit"),
    "selected": ("miss", "hit"),
    "forbid": ("violated", "ok"),
    "noise": ("noisy", "clean"),
}


def render_comparison(c: Comparison) -> Group:
    parts: list = [
        Text(f"Comparing {c.a_label} -> {c.b_label}", style="bold"),
        Text(f"{c.queries_compared} queries compared"),
    ]
    if not c.same_fixtures:
        parts.append(
            Text(
                "Different fixtures: only queries with the same id are matched, and the "
                "overall numbers cover different query sets.",
                style="yellow",
            )
        )
    if c.settings:
        table = _table(
            "Settings that differ",
            ["Setting", c.a_label, c.b_label],
            caption="Changes below may come from these settings as well as from code changes.",
        )
        for diff in c.settings:
            _row(table, diff.field, diff.before, diff.after)
        parts += [Text(""), table]

    metrics = _table(
        "Metrics", ["Metric", c.a_label, c.b_label, "Change", "Verdict"],
        right={c.a_label, c.b_label, "Change"},
    )
    for m in c.metrics:
        _row(metrics, m.label, m.before, m.after, _change(m),
             Text(m.verdict, style=_VERDICT_STYLE.get(m.verdict, "")))
    parts += [Text(""), metrics]

    if c.flips:
        flips = _table("Queries that changed", ["View", "Query", "Before", "After", "Split"])
        for f in c.flips:
            bad, good = _STATES[f.view]
            style = "green" if f.after else "red"
            _row(flips, f.view, f.id, bad if not f.before else good,
                 Text(bad if not f.after else good, style=style), f.split or "-")
        parts += [Text(""), flips]
    else:
        parts += [Text(""), Text("No query changed status.")]

    parts.append(Text(""))
    for view in ("candidates", "selected"):
        net = c.net(view)
        parts.append(
            Text(
                f"{view.capitalize()} hits: net {net:+d} "
                f"(gained {c.count(view, gained=True)}, lost {c.count(view, gained=False)})"
            )
        )
    verdict = c.ship_rule_ok
    if verdict is None:
        parts.append(Text("Ship rule: not judged (different fixtures)."))
    elif verdict:
        parts.append(Text("Ship rule (at most 1 net query lost): met.", style="green"))
    else:
        parts.append(Text("Ship rule (at most 1 net query lost): NOT met.", style="red"))
    if c.only_in_a:
        parts.append(Text(f"Only in {c.a_label}: {', '.join(c.only_in_a)}"))
    if c.only_in_b:
        parts.append(Text(f"Only in {c.b_label}: {', '.join(c.only_in_b)}"))
    return Group(*parts)


# --- Saved runs -----------------------------------------------------------------------


def render_run_list(listings: Sequence[RunListing], directory: Path | str) -> Group | Text:
    if not listings:
        return Text(f"No saved runs in {directory}.")
    table = _table(
        f"Saved runs in {directory}",
        ["Name", "Created", "Fixtures", "Hash", "k", "Candidate hits", "Selected hits"],
        right={"k"},
    )
    for item in listings:
        if item.error:
            _row(table, item.name, "", Text(f"unreadable: {item.error}", style="red"), "", "", "", "")
        else:
            _row(table, item.name, item.created_at, item.fixture_name,
                 (item.fixture_hash or "")[:12], item.k, item.candidate_hits, item.selected_hits)
    return Group(table)