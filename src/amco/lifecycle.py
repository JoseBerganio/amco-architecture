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

"""Memory lifecycle review: suggests, and optionally applies, housekeeping changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import lifecycle_settings
from .ranking import parse_timestamp
from .storage import (
    delete_memory,
    list_memories,
    memory_status,
    normalize_content,
    supersede_memory,
    update_memory,
)


@dataclass(frozen=True)
class Finding:
    memory_id: int
    action: str            # delete | archive | promote | supersede
    reason: str
    target_id: int | None = None   # the replacement, for "supersede"


def _last_activity(memory: dict) -> datetime | None:
    stamps = [parse_timestamp(memory.get(k)) for k in ("last_used_at", "updated_at", "created_at")]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def review(db_path: Path | None = None, now: datetime | None = None) -> list[Finding]:
    """Inspect all memories and return suggested changes. Nothing is modified."""
    now = now or datetime.now(timezone.utc)
    stale_days, promote_uses, retention_days = lifecycle_settings()
    today = now.date().isoformat()
    memories = list_memories(db_path=db_path, include_inactive=True)
    findings: list[Finding] = []

    # Exact duplicates among active memories: keep the most trusted, supersede the rest.
    groups: dict[str, list[dict]] = {}
    for m in memories:
        if memory_status(m, today) == "active":
            groups.setdefault(normalize_content(m["content"]), []).append(m)
    losers: set[int] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        keeper = max(group, key=lambda m: (m["confidence"], m["updated_at"] or "", m["id"]))
        for m in group:
            if m["id"] != keeper["id"]:
                losers.add(m["id"])
                findings.append(
                    Finding(m["id"], "supersede", f"duplicate of #{keeper['id']}", keeper["id"])
                )

    for m in memories:
        status = memory_status(m, today)
        if status == "expired":
            findings.append(Finding(m["id"], "delete", f"expired on {m['expires_at']}"))
            continue
        if status == "superseded":
            since = parse_timestamp(m["superseded_at"])
            if since is not None:
                days = (now - since).days
                if days >= retention_days:
                    findings.append(
                        Finding(
                            m["id"], "delete",
                            f"superseded by #{m['superseded_by']} {days} days ago",
                        )
                    )
            continue
        if m["id"] in losers:
            continue

        last = _last_activity(m)
        idle_days = (now - last).days if last else 0
        if m["memory_type"] == "persistent" and idle_days >= stale_days:
            findings.append(
                Finding(m["id"], "archive", f"not used or edited for {idle_days} days")
            )
        elif (
            m["memory_type"] == "long_term"
            and m["use_count"] >= promote_uses
            and idle_days < stale_days
        ):
            findings.append(
                Finding(m["id"], "promote", f"used {m['use_count']} times and still active")
            )

    findings.sort(key=lambda f: f.memory_id)
    return findings


def apply_finding(finding: Finding, db_path: Path | None = None) -> bool:
    """Carry out one finding. Raises ValueError if it no longer applies."""
    if finding.action == "delete":
        return delete_memory(finding.memory_id, db_path=db_path)
    if finding.action == "archive":
        return update_memory(finding.memory_id, memory_type="long_term", db_path=db_path)
    if finding.action == "promote":
        return update_memory(finding.memory_id, memory_type="persistent", db_path=db_path)
    if finding.action == "supersede" and finding.target_id is not None:
        return supersede_memory(finding.memory_id, finding.target_id, db_path=db_path)
    raise ValueError(f"Unknown action: {finding.action}")