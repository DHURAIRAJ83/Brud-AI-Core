"""MB-10: Duplicate Resolver -- pure. Classifies already-detected
duplicate groups (from the existing `ExternalDatasetDuplicateService.
group_normalized_duplicates()`, reused unchanged -- this module never
re-detects duplicates itself) into a resolution recommendation. Never
merges anything automatically.
"""

from __future__ import annotations

from typing import Any


def resolve_duplicates(*, duplicate_groups: list[list[str]], provider_count: int) -> dict[str, Any]:
    resolutions = [
        {
            "providers": group,
            "recommendation": f"{len(group)} provider(s) gave near-identical answers -- treat as one data point, not independent confirmation",
        }
        for group in duplicate_groups
    ]
    duplicated_provider_count = len({provider for group in duplicate_groups for provider in group})
    independent_signal_count = max(provider_count - duplicated_provider_count, 0) + len(duplicate_groups)

    duplicate_score = 100.0 if not duplicate_groups else max(0.0, 100.0 - duplicated_provider_count * 15.0)
    return {
        "duplicate_group_count": len(duplicate_groups),
        "duplicated_provider_count": duplicated_provider_count,
        "independent_signal_count": independent_signal_count,
        "resolutions": resolutions,
        "duplicate_score": round(duplicate_score, 1),
    }
