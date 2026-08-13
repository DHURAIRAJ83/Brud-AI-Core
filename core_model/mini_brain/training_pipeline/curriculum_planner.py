"""MB-18: Curriculum Planner -- pure. Orders MB-16's own record types
into a simple easy-to-hard curriculum using a fixed, disclosed
difficulty ranking -- never a learned or data-driven difficulty score,
since no training has ever run to measure one.
"""

from __future__ import annotations

from typing import Any

DIFFICULTY_ORDER = (
    "instruction", "training", "conversation", "qa", "caption", "vision", "grounding", "reasoning",
)


def plan_curriculum(*, record_type_counts: dict[str, int]) -> dict[str, Any]:
    stages = []
    for rank, record_type in enumerate(DIFFICULTY_ORDER, start=1):
        count = record_type_counts.get(record_type, 0)
        if count > 0:
            stages.append({"rank": rank, "record_type": record_type, "record_count": count})

    unranked = sorted(set(record_type_counts) - set(DIFFICULTY_ORDER))
    for record_type in unranked:
        stages.append({"rank": len(DIFFICULTY_ORDER) + 1, "record_type": record_type, "record_count": record_type_counts[record_type]})

    return {
        "stages": stages, "stage_count": len(stages),
        "total_records": sum(record_type_counts.values()),
        "disclosure": (
            "a fixed, disclosed easy-to-hard ordering by record type -- never a learned or "
            "data-driven difficulty score, since no training has ever run in this codebase to measure one"
        ),
    }
