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

"""The `amco eval` command group: run the benchmark, compare saved runs, list them.

Thin glue only. Running, scoring, saving, comparing and rendering all live in
amco.evaluation, and these commands never open the user's memory database.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Callable, List, Optional

import typer

from ..config import eval_dir
from ..evaluation import (
    DEFAULT_K,
    FixtureError,
    RunError,
    SavedRun,
    check_gates,
    collect_meta,
    compare_runs,
    dumps_run,
    list_runs,
    load_fixtures,
    load_run_file,
    render_comparison,
    render_run,
    render_run_list,
    resolve_run,
    run_path,
    run_suite,
    save_run,
    select_queries,
    write_run_file,
)
from .common import console, err_console

eval_app = typer.Typer(
    help="Measure retrieval quality on a fixed benchmark.", no_args_is_help=True
)

_NOTE_TIP = (
    'Tip: add --note with the git commit (for example --note "$(git rev-parse --short HEAD)") '
    "so this run can be traced to its code."
)


def handle_eval_errors(command: Callable[..., Any]) -> Callable[..., Any]:
    """Turn fixture and run-file problems into one clear message and exit code 1.

    Only these two error types are caught, so a genuine bug still shows a traceback.
    """

    @functools.wraps(command)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return command(*args, **kwargs)
        except (FixtureError, RunError) as exc:
            err_console.print(str(exc), markup=False, highlight=False)
            raise typer.Exit(code=1) from exc

    return wrapper


def _refuse_existing(path: Path, what: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise RunError(f"{what} already exists ({path}). Choose another name, or pass --overwrite.")


def _preflight(save: Optional[str], out: Optional[Path], overwrite: bool) -> None:
    """Fail on a bad or taken name BEFORE spending time on a run."""
    if save is not None:
        _refuse_existing(run_path(save), f"A saved run named '{save}'", overwrite)
    if out is not None:
        _refuse_existing(Path(out), "The output file", overwrite)


@eval_app.command("run")
@handle_eval_errors
def eval_run(
    fixtures: Optional[Path] = typer.Option(
        None, "--fixtures", help="Fixtures file (default: the packaged benchmark)."
    ),
    k: int = typer.Option(DEFAULT_K, "--k", min=1, help="Top-k cut-off for retrieval metrics."),
    tag: Optional[List[str]] = typer.Option(
        None, "--tag", help="Only run queries with this tag (repeatable)."
    ),
    save: Optional[str] = typer.Option(
        None, "--save", help="Save the run under this name in the eval folder."
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", help="Also write the run to this file (for example a committed baseline)."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace an existing saved run or --out file."
    ),
    note: Optional[str] = typer.Option(
        None, "--note", help="Free text stored with the run, such as a git commit."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="List every query that needs attention."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Print the run as JSON instead of tables."
    ),
    min_recall: Optional[float] = typer.Option(
        None, "--min-recall", min=0.0, max=1.0,
        help="Exit with code 1 if candidate recall@k is below this.",
    ),
    min_mrr: Optional[float] = typer.Option(
        None, "--min-mrr", min=0.0, max=1.0,
        help="Exit with code 1 if candidate MRR is below this.",
    ),
) -> None:
    """Run the benchmark through the real retrieval pipeline and report the results."""
    _preflight(save, out, overwrite)
    fixture_set = load_fixtures(fixtures)
    tags = list(tag) if tag else None
    try:
        select_queries(fixture_set, tags)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--tag") from exc

    suite = run_suite(fixture_set, k=k, tags=tags)
    run = SavedRun(collect_meta(tags=tags, note=note), suite)

    notices: list[str] = []
    if save is not None:  # saved before the gates, so a failing run is still recorded
        notices.append(f"Saved run '{save}' to {save_run(save, run, overwrite=overwrite)}")
    if out is not None:
        notices.append(f"Wrote run to {write_run_file(out, run)}")
    if notices and note is None:
        notices.append(_NOTE_TIP)

    if as_json:
        typer.echo(dumps_run(run), nl=False)
    else:
        console.print(render_run(run, name=save, verbose=verbose))
    notice_console = err_console if as_json else console
    for line in notices:
        notice_console.print(line, markup=False, highlight=False)

    failures = check_gates(suite.overall, min_recall, min_mrr)
    for message in failures:
        err_console.print(message, markup=False, highlight=False)
    if failures:
        raise typer.Exit(code=1)


@eval_app.command("compare")
@handle_eval_errors
def eval_compare(
    a: str = typer.Argument(..., help="Run before: a saved name or a file path."),
    b: str = typer.Argument(..., help="Run after: a saved name or a file path."),
    force: bool = typer.Option(
        False, "--force", help="Compare even if the runs used different fixtures."
    ),
    check: bool = typer.Option(
        False, "--check", help="Exit with code 1 unless the ship rule is met."
    ),
) -> None:
    """Compare two saved runs: metric changes and which queries flipped."""
    path_a, path_b = resolve_run(a), resolve_run(b)
    label_a, label_b = path_a.stem, path_b.stem
    if label_a == label_b:
        label_a, label_b = f"{label_a} (A)", f"{label_b} (B)"
    comparison = compare_runs(
        load_run_file(path_a), load_run_file(path_b), label_a, label_b, force=force
    )
    console.print(render_comparison(comparison))
    if check and comparison.ship_rule_ok is not True:
        reason = (
            "the runs used different fixtures, so it cannot be judged"
            if comparison.ship_rule_ok is None
            else "more than 1 net query was lost"
        )
        err_console.print(f"Ship rule not met: {reason}.", markup=False, highlight=False)
        raise typer.Exit(code=1)


@eval_app.command("list")
@handle_eval_errors
def eval_list() -> None:
    """List saved evaluation runs."""
    folder = eval_dir()
    console.print(render_run_list(list_runs(folder), folder))