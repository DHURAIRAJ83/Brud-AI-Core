"""MB-12: Knowledge Lifecycle Timeline -- pure. Sorts and normalizes
already-fetched event entries from every linked phase (MB-09, MB-10,
MB-11, MB-06) into one chronological timeline. Never fetches an event
itself -- the service reads each phase's own `.events()`/`.session()`
output and passes the raw entries in.
"""

from __future__ import annotations

from typing import Any


def build_timeline(*, entries: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_entries = sorted(entries, key=lambda e: e["created_at"])
    phase_counts: dict[str, int] = {}
    for entry in sorted_entries:
        phase_counts[entry["phase"]] = phase_counts.get(entry["phase"], 0) + 1

    return {
        "timeline": sorted_entries,
        "event_count": len(sorted_entries),
        "phase_counts": phase_counts,
        "first_event_at": sorted_entries[0]["created_at"] if sorted_entries else None,
        "last_event_at": sorted_entries[-1]["created_at"] if sorted_entries else None,
    }
