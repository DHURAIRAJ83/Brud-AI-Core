"""MB-22: Training Audit Builder -- pure. Summarizes an already-
fetched event list into a compact audit trail -- never recomputes or
re-derives what happened, only summarizes the real, already-recorded
events.
"""

from __future__ import annotations

from typing import Any


def build_training_audit(*, events: list[dict[str, Any]], admin_authorized_by: str | None) -> dict[str, Any]:
    event_type_counts: dict[str, int] = {}
    for event in events:
        event_type_counts[event["event_type"]] = event_type_counts.get(event["event_type"], 0) + 1

    return {
        "event_count": len(events), "event_type_counts": event_type_counts,
        "admin_authorized_by": admin_authorized_by,
        "timeline": [
            {"created_at": e["created_at"], "event_type": e["event_type"], "stage": e.get("stage")}
            for e in events
        ],
        "disclosure": "a summary of this job's own already-recorded append-only event log -- nothing here is re-derived or inferred",
    }
