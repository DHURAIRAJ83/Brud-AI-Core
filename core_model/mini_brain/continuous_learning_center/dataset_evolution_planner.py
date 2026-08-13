"""MB-09: Dataset Evolution Planner -- pure. Compares an existing
dataset's already-computed MB-05 training-readiness summary against a
new local draft's topic, and recommends merge / extend / replace /
split / ignore. Never performs the merge -- Dataset Studio remains the
only place a dataset is actually changed.
"""

from __future__ import annotations

from typing import Any

LARGE_DATASET_RECORD_THRESHOLD = 1000
HEALTHY_CLEAN_RATIO = 0.9
HEALTHY_DUPLICATE_RATIO = 0.02
HIGH_DUPLICATE_RATIO = 0.3


def plan_dataset_evolution(
    *, existing_dataset_exists: bool, draft_topic: str, existing_status: str | None = None,
    existing_clean_ratio: float | None = None, existing_duplicate_ratio: float | None = None,
    existing_record_count: int | None = None,
) -> dict[str, Any]:
    evidence = {
        "existing_dataset_exists": existing_dataset_exists, "existing_status": existing_status,
        "existing_clean_ratio": existing_clean_ratio, "existing_duplicate_ratio": existing_duplicate_ratio,
        "existing_record_count": existing_record_count,
    }

    if not existing_dataset_exists:
        return {
            "recommendation": "extend",
            "why": f"no existing dataset source was supplied for '{draft_topic}' -- extend by adding new content once written",
            "evidence": evidence,
        }

    if existing_status == "Not Ready" and (existing_duplicate_ratio or 0) > HIGH_DUPLICATE_RATIO:
        return {
            "recommendation": "replace",
            "why": (
                f"existing dataset is 'Not Ready' with a {existing_duplicate_ratio} duplicate ratio "
                f"above {HIGH_DUPLICATE_RATIO} -- replacing is likely more effective than patching"
            ),
            "evidence": evidence,
        }

    if existing_status == "Not Ready":
        return {
            "recommendation": "extend",
            "why": "existing dataset is 'Not Ready' but not heavily duplicated -- extend it with the new draft's content",
            "evidence": evidence,
        }

    if existing_record_count is not None and existing_record_count > LARGE_DATASET_RECORD_THRESHOLD:
        return {
            "recommendation": "split",
            "why": (
                f"existing dataset has {existing_record_count} records (above {LARGE_DATASET_RECORD_THRESHOLD}) "
                f"-- split out a '{draft_topic}'-focused subset before merging new content"
            ),
            "evidence": evidence,
        }

    if (
        existing_status == "Ready"
        and (existing_clean_ratio or 0) >= HEALTHY_CLEAN_RATIO
        and (existing_duplicate_ratio if existing_duplicate_ratio is not None else 1) <= HEALTHY_DUPLICATE_RATIO
    ):
        return {
            "recommendation": "ignore",
            "why": f"existing dataset is already healthy (clean_ratio={existing_clean_ratio}, duplicate_ratio={existing_duplicate_ratio}) -- no evolution needed for '{draft_topic}'",
            "evidence": evidence,
        }

    return {
        "recommendation": "merge",
        "why": f"existing dataset is healthy enough (status={existing_status}) to directly incorporate the new draft for '{draft_topic}'",
        "evidence": evidence,
    }
