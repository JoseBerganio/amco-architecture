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

"""Safety copies taken before a database is upgraded.

Uses SQLite's online backup API, which produces a consistent copy even if
another connection is open. Standard library only.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_path(db_path: Path, version: int) -> Path:
    """Where the backup for `version` goes. Never returns a path that already exists.

    First choice is `<name>.bak-v<version>`. If that is taken, a timestamp
    (and a counter, if needed) is added, so an older backup is never overwritten.
    """
    plain = db_path.with_name(f"{db_path.name}.bak-v{version}")
    if not plain.exists():
        return plain
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = db_path.with_name(f"{plain.name}-{stamp}")
    counter = 2
    while candidate.exists():
        candidate = db_path.with_name(f"{plain.name}-{stamp}-{counter}")
        counter += 1
    return candidate


def backup_database(conn: sqlite3.Connection, db_path: Path, version: int) -> Path:
    """Copy the database behind `conn` next to itself and return the copy's path.

    A partly written copy is deleted if the backup fails. The caller decides
    what a failure means; this function lets sqlite3.Error and OSError through.
    """
    target = backup_path(db_path, version)
    destination = sqlite3.connect(target)
    try:
        conn.backup(destination)
    except BaseException:
        destination.close()  # close first: Windows cannot delete an open file
        target.unlink(missing_ok=True)
        raise
    destination.close()
    logger.warning(
        "AMCO is upgrading the database (schema version %d). A backup was saved to: %s",
        version,
        target,
    )
    return target