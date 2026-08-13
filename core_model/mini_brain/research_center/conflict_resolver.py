"""MB-10: Conflict Resolver -- pure. Classifies already-detected
conflicts (from the existing `ExternalDatasetDuplicateService.
find_conflicts()`, reused unchanged -- this module never re-detects
conflicts itself) into a resolution recommendation. Never resolves a
conflict automatically -- every classification here still requires an
admin decision downstream.
"""

from __future__ import annotations

from typing import Any


def resolve_conflicts(*, conflict_groups: list[dict[str, Any]], provider_count: int) -> dict[str, Any]:
    resolutions = []
    for group in conflict_groups:
        distinct_values = group.get("conflicting_values") or group.get("values") or []
        value_count = len(distinct_values) if isinstance(distinct_values, list) else 0
        if provider_count >= 3 and value_count == 2:
            recommendation = "majority_available -- admin review recommended before trusting the majority"
        else:
            recommendation = "no_majority -- admin review required, providers are evenly split or too few responded"
        resolutions.append({"conflict": group, "recommendation": recommendation})

    conflict_score = max(0.0, 100.0 - len(conflict_groups) * 25.0)
    return {
        "conflict_count": len(conflict_groups),
        "resolutions": resolutions,
        "conflict_score": round(conflict_score, 1),
        "has_unresolved_conflicts": bool(conflict_groups),
    }
