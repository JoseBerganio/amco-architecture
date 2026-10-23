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

from __future__ import annotations

import re

STOPWORDS = frozenset("""
a an the and or but if of to in on at by for with about as from into is are was were be been am
do does did it its this that these those i you he she we they me my your our their what which who
whom when where why how can could should would will shall may might must not no so than then there
here have has had any some please tell hi hello hey thanks thank ok okay
""".split())

_TOKEN_RE = re.compile(r"[^\W_]+")


def normalize_content(text: str) -> str:
    """Case, whitespace and trailing punctuation do not make a memory different."""
    return " ".join(text.casefold().split()).rstrip(".!? ")


def term_similarity(a: str, b: str) -> float:
    """Jaccard overlap (0 to 1) of the meaningful terms of two texts."""
    terms_a, terms_b = set(extract_terms(a)), set(extract_terms(b))
    if not terms_a or not terms_b:
        return 0.0
    return len(terms_a & terms_b) / len(terms_a | terms_b)


def extract_terms(text: str, limit: int | None = None) -> list[str]:
    """Meaningful lowercase terms: no punctuation, stopwords, one-letter tokens or duplicates."""
    terms: list[str] = []
    for token in _TOKEN_RE.findall(text.casefold()):
        if len(token) < 2 or token in STOPWORDS or token in terms:
            continue
        terms.append(token)
    return terms if limit is None else terms[:limit]