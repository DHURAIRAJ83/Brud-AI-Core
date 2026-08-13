"""MB-11: Dataset Expansion Planner -- pure. Recommends exactly one of
merge / extend / split / replace / archive / create_new from
already-computed dataset-readiness, coverage-classification, and
knowledge-relationship signals. Never performs the recommended
action -- Dataset Studio remains the only place a dataset is actually
changed, and only after an admin decides to act on this plan.
"""

from __future__ import annotations

from typing import Any

LARGE_DATASET_RECORD_THRESHOLD = 1000
HIGH_DUPLICATE_RATIO = 0.3
LOW_PRESSURE_THRESHOLD = 10.0
STAGNANT_STATUSES = {"Not Ready", "Needs Improvement"}


def plan_expansion(
    *,
    dataset_status: str,
    duplicate_ratio: float,
    record_count: int,
    coverage_summary: dict[str, Any],
    relationship_report: dict[str, Any],
    evolution_pressure: float,
) -> dict[str, Any]:
    evidence = {
        "dataset_status": dataset_status, "duplicate_ratio": duplicate_ratio, "record_count": record_count,
        "critical_gap_count": coverage_summary["critical_gap_count"],
        "needs_expansion_count": coverage_summary["needs_expansion_count"],
        "duplicate_knowledge_count": relationship_report["duplicate_knowledge_count"],
        "evolution_pressure": evolution_pressure,
    }

    if dataset_status == "Not Ready" and duplicate_ratio > HIGH_DUPLICATE_RATIO:
        return {
            "action": "replace",
            "why": f"dataset is 'Not Ready' with a {duplicate_ratio} duplicate ratio above {HIGH_DUPLICATE_RATIO} -- replacing is likely more effective than patching",
            "evidence": evidence,
        }

    if coverage_summary["critical_gap_count"] >= 3:
        return {
            "action": "create_new",
            "why": f"{coverage_summary['critical_gap_count']} dimension(s) are at Critical Gap -- too many and too large to close by extending the existing dataset",
            "evidence": evidence,
        }

    if relationship_report["duplicate_knowledge_count"] >= 2:
        return {
            "action": "merge",
            "why": f"{relationship_report['duplicate_knowledge_count']} redundant weak-domain signal(s) recur across MB-08/MB-09/MB-10 -- consolidate before adding more content",
            "evidence": evidence,
        }

    if (
        record_count > LARGE_DATASET_RECORD_THRESHOLD
        and coverage_summary["critical_gap_count"] == 0
        and coverage_summary["needs_expansion_count"] == 0
    ):
        return {
            "action": "split",
            "why": f"dataset already has {record_count} records (above {LARGE_DATASET_RECORD_THRESHOLD}) with no coverage gaps -- split into focused subsets rather than growing further",
            "evidence": evidence,
        }

    if dataset_status in STAGNANT_STATUSES and evolution_pressure < LOW_PRESSURE_THRESHOLD:
        return {
            "action": "archive",
            "why": f"dataset status is '{dataset_status}' but evolution pressure ({evolution_pressure}) is below {LOW_PRESSURE_THRESHOLD} -- neither improving nor actively needed, not worth further investment as-is",
            "evidence": evidence,
        }

    return {
        "action": "extend",
        "why": "no single dimension is critical enough to replace/split/merge/archive/create-new -- incremental extension is the safest next step",
        "evidence": evidence,
    }
