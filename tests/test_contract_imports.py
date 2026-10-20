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

"""Contract: every name in SPRINT.md section 5 must stay importable from its module."""

import importlib

import pytest

SURFACE = {
    "amco.storage": [
        "DEFAULT_DB", "VALID_TYPES", "DEFAULT_CONFIDENCE", "MAX_QUERY_TERMS",
        "SIMILARITY_THRESHOLD", "STOPWORDS", "database_path", "connect", "session",
        "memory_status", "add_memory", "list_memories", "get_memory", "update_memory",
        "delete_memory", "supersede_memory", "restore_memory", "normalize_content",
        "term_similarity", "check_duplicates", "extract_terms", "search_candidates",
        "search_memories", "record_usage", "rebuild_index", "_has_fts",
    ],
    "amco.engine": [
        "answer", "select_memories", "retrieval_query", "ollama_chat",
        "context_settings", "SYSTEM_PROMPT", "format_memory",
    ],
    "amco.model": ["ollama_chat", "httpx"],
    "amco.cli": ["app", "answer"],
    "amco.ame": [
        "analyze_task", "retrieve", "resolve_duplicates", "detect_conflicts",
        "select_within_budget", "format_memory", "prepare", "finish",
        "SYSTEM_PROMPT", "TaskAnalysis", "ContextReport", "PreparedContext",
    ],
    "amco.ranking": [
        "RankingWeights", "weights_from_env", "parse_timestamp", "freshness",
        "usefulness", "rank_memories",
    ],
    "amco.working": ["WorkingMemory", "Turn", "estimate_tokens"],
    "amco.lifecycle": ["Finding", "review", "apply_finding"],
    "amco.config": [
        "model_name", "ollama_url", "int_env", "float_env", "context_settings",
        "freshness_half_life_days", "followup_settings", "lifecycle_settings",
        "DEFAULT_TIMEOUT_SECONDS",
    ],
}

CASES = [(module, name) for module, names in SURFACE.items() for name in names]


@pytest.mark.parametrize("module, name", CASES)
def test_name_is_importable(module, name):
    assert hasattr(importlib.import_module(module), name), f"{module}.{name} is missing"


def test_console_script_target_exists():
    from amco.cli import app

    assert callable(app)