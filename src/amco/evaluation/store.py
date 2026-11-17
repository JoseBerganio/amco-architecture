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

"""Save, find, load and list evaluation runs on disk.

A run's name is its file name: <eval folder>/<name>.json. Any other path can be
used with write_run_file / load_run_file, for example a committed baseline in benchmarks/.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..config import eval_dir
from .run_record import RunError, SavedRun
from .serialize import dumps_run, loads_run

# Starts with a letter or digit, so '.', '..' and hidden-file names are impossible.
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
SUFFIX = ".json"


def check_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not NAME_RE.fullmatch(name)
        or name.casefold().endswith(SUFFIX)
    ):
        raise RunError(
            "Run names use letters, digits, '.', '_' and '-', start with a letter or digit, "
            "are at most 64 characters long, and must not end in .json."
        )
    return name


def _folder(directory: Path | str | None) -> Path:
    return Path(directory) if directory is not None else eval_dir()


def run_path(name: str, directory: Path | str | None = None) -> Path:
    return _folder(directory) / f"{check_name(name)}{SUFFIX}"


# --- Writing -------------------------------------------------------------------


def write_run_file(path: Path | str, run: SavedRun) -> Path:
    """Write atomically: a temp file in the same folder, then a rename.

    A crash can never leave a half-written run. Bytes are UTF-8 with "\\n" line
    endings on every platform, so a committed baseline does not change on Windows.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".amco-run-", suffix=".tmp")
    except OSError as exc:
        raise RunError(f"Cannot write {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(dumps_run(run).encode("utf-8"))
        os.replace(tmp_name, path)
    except OSError as exc:
        Path(tmp_name).unlink(missing_ok=True)
        raise RunError(f"Cannot write {path}: {exc}") from exc
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return path


def save_run(
    name: str, run: SavedRun, directory: Path | str | None = None, overwrite: bool = False
) -> Path:
    """Save under the eval folder. An existing name is refused unless overwrite is set."""
    path = run_path(name, directory)
    if path.exists() and not overwrite:
        raise RunError(
            f"A saved run named '{name}' already exists ({path}). "
            "Choose another name, or overwrite it on purpose."
        )
    return write_run_file(path, run)


# --- Reading -------------------------------------------------------------------


def load_run_file(path: Path | str) -> SavedRun:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Windows editors
    except (OSError, UnicodeDecodeError) as exc:
        raise RunError(f"Cannot read {path}: {exc}") from exc
    try:
        return loads_run(text)
    except RunError as exc:
        raise RunError(f"{path}: {exc}") from exc


def saved_names(directory: Path | str | None = None) -> list[str]:
    folder = _folder(directory)
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob(f"*{SUFFIX}") if p.is_file())


def resolve_run(ref: str, directory: Path | str | None = None) -> Path:
    """A saved name in the eval folder wins; otherwise `ref` is treated as a file path."""
    folder = _folder(directory)
    if NAME_RE.fullmatch(ref) and not ref.casefold().endswith(SUFFIX):
        candidate = folder / f"{ref}{SUFFIX}"
        if candidate.is_file():
            return candidate
    as_path = Path(ref)
    if as_path.is_file():
        return as_path
    names = saved_names(folder)
    shown = ", ".join(names[:10]) + (" ..." if len(names) > 10 else "") if names else "none"
    raise RunError(
        f"No saved run '{ref}'. Looked for {folder / (ref + SUFFIX)} and for a file at that path. "
        f"Saved runs: {shown}."
    )


def load_run(ref: str, directory: Path | str | None = None) -> SavedRun:
    return load_run_file(resolve_run(ref, directory))


# --- Listing -------------------------------------------------------------------


@dataclass(frozen=True)
class RunListing:
    name: str
    path: Path
    created_at: str | None = None
    fixture_name: str | None = None
    fixture_hash: str | None = None
    k: int | None = None
    candidate_hits: str | None = None
    selected_hits: str | None = None
    error: str | None = None


def list_runs(directory: Path | str | None = None) -> list[RunListing]:
    """One entry per .json file. An unreadable file is listed with its error, not skipped."""
    folder = _folder(directory)
    if not folder.is_dir():
        return []
    listings: list[RunListing] = []
    for path in sorted(folder.glob(f"*{SUFFIX}")):
        if not path.is_file():
            continue
        try:
            run = load_run_file(path)
        except RunError as exc:
            listings.append(RunListing(name=path.stem, path=path, error=str(exc)))
            continue
        overall = run.suite.overall
        listings.append(
            RunListing(
                name=path.stem,
                path=path,
                created_at=run.meta.created_at,
                fixture_name=run.suite.fixture_name,
                fixture_hash=run.suite.fixture_hash,
                k=run.suite.k,
                candidate_hits=str(overall.candidates.hits),
                selected_hits=str(overall.selected.hits),
            )
        )
    return listings