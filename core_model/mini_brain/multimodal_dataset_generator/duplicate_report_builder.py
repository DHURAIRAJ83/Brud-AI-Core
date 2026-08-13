"""MB-16: Duplicate Detection report -- pure. Summarizes duplicate
groups already computed by the existing, reused `ExternalDatasetDuplicateService`
(Phase 12) -- never a new duplicate-matching implementation. Covers
records, images (by checksum), conversations, QA, and captions -- all
through the same generic record-checksum grouping.
"""

from __future__ import annotations

from typing import Any


def build_duplicate_report(
    *, exact_groups: list[list[str]], normalized_groups: list[list[str]], image_checksum_groups: list[list[str]],
) -> dict[str, Any]:
    return {
        "exact_duplicate_groups": exact_groups,
        "exact_duplicate_count": sum(len(g) for g in exact_groups),
        "normalized_duplicate_groups": normalized_groups,
        "normalized_duplicate_count": sum(len(g) for g in normalized_groups),
        "image_duplicate_groups": image_checksum_groups,
        "image_duplicate_count": sum(len(g) for g in image_checksum_groups),
        "reused_service": "ExternalDatasetDuplicateService (Phase 12) -- group_exact_duplicates() / group_normalized_duplicates()",
    }
