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

"""AMCO storage package: SQLite connection, memory records, hygiene and search.

Everything public is re-exported here, so `from amco.storage import ...` keeps working.
"""

from __future__ import annotations

from ..config import DEFAULT_DB, database_path
from .db import connect, rebuild_index, session
from .hygiene import (
    SIMILARITY_THRESHOLD,
    check_duplicates,
    restore_memory,
    supersede_memory,
)
from .memories import (
    DEFAULT_CONFIDENCE,
    VALID_TYPES,
    add_memory,
    delete_memory,
    get_memory,
    list_memories,
    memory_status,
    record_usage,
    update_memory,
)
from .search import MAX_QUERY_TERMS, search_candidates, search_memories
from .schema import SCHEMA_VERSION, SchemaError
from .text import STOPWORDS, extract_terms, normalize_content, term_similarity

__all__ = [
    "DEFAULT_CONFIDENCE",
    "DEFAULT_DB",
    "MAX_QUERY_TERMS",
    "SCHEMA_VERSION",
    "SIMILARITY_THRESHOLD",
    "STOPWORDS",
    "SchemaError",
    "VALID_TYPES",
    "add_memory",
    "check_duplicates",
    "connect",
    "database_path",
    "delete_memory",
    "extract_terms",
    "get_memory",
    "list_memories",
    "memory_status",
    "normalize_content",
    "rebuild_index",
    "record_usage",
    "restore_memory",
    "search_candidates",
    "search_memories",
    "session",
    "supersede_memory",
    "term_similarity",
    "update_memory",
]
