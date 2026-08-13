"""MB-09: Continuous Learning Queue -- pure. Turns already-computed
recurring weak domains into a prioritized queue. Queue only -- never
creates a dataset, never writes anything outside the queue itself.
"""

from __future__ import annotations

from typing import Any

_PRIORITY_BANDS = ((150.0, "Critical"), (80.0, "High"), (30.0, "Medium"))
_EFFORT_BANDS = ((5, "Large"), (3, "Medium"))


def _priority_for(importance: float) -> str:
    for threshold, label in _PRIORITY_BANDS:
        if importance >= threshold:
            return label
    return "Low"


def _effort_for(recurrence_count: int) -> str:
    for threshold, label in _EFFORT_BANDS:
        if recurrence_count >= threshold:
            return label
    return "Small"


def build_learning_queue(
    *, recurring_weak_domains: list[dict[str, Any]], latest_dataset_suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    suggestions_by_domain = {s["domain"]: s for s in latest_dataset_suggestions}

    items = []
    for entry in recurring_weak_domains:
        domain = entry["domain"]
        suggestion = suggestions_by_domain.get(domain)
        dataset_types = (
            sorted({fmt["format"] for fmt in suggestion["recommended_formats"]})
            if suggestion else ["QA pairs"]
        )
        items.append({
            "topic": domain,
            "reason": f"weak in {entry['recurrence_count']} of the compared learning cycle(s)",
            "evidence": {
                "recurrence_count": entry["recurrence_count"],
                "latest_weakness_index": entry["latest_weakness_index"],
                "long_term_importance": entry["long_term_importance"],
            },
            "priority": _priority_for(entry["long_term_importance"]),
            "suggested_dataset_type": dataset_types,
            "estimated_effort": _effort_for(entry["recurrence_count"]),
        })

    return {"queue": items, "queue_length": len(items)}
