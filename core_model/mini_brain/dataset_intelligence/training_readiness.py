"""MB-05: Training Readiness Analyzer -- Ready / Needs Improvement /
Not Ready, always with explicit reasons, built entirely from the
already-computed Quality and Duplicate analyses (composition, not
re-derivation). This is advisory only: it returns a verdict string and
never calls any approval, training-start, or dataset-modification API
-- "Never automatically approve" is enforced structurally by this
module having no access to any writable service at all.
"""

from __future__ import annotations

from typing import Any

MIN_RECORDS_FOR_TRAINING = 50
READY_CLEAN_RATIO = 0.85
NEEDS_IMPROVEMENT_CLEAN_RATIO = 0.5
READY_DUPLICATE_RATIO = 0.05
NOT_READY_DUPLICATE_RATIO = 0.20


def assess_training_readiness(
    *, record_count: int, quality: dict[str, Any], duplicates: dict[str, Any],
) -> dict[str, Any]:
    clean_ratio = quality.get("clean_ratio") or 0.0
    duplicate_ratio = (duplicates["duplicate_record_count"] / record_count) if record_count else 0.0

    blockers: list[str] = []
    if record_count < MIN_RECORDS_FOR_TRAINING:
        blockers.append(f"only {record_count} records -- below the {MIN_RECORDS_FOR_TRAINING}-record minimum")
    if clean_ratio < NEEDS_IMPROVEMENT_CLEAN_RATIO:
        blockers.append(f"clean_ratio {clean_ratio} is below {NEEDS_IMPROVEMENT_CLEAN_RATIO} -- too many quality issues")
    if duplicate_ratio > NOT_READY_DUPLICATE_RATIO:
        blockers.append(
            f"{round(duplicate_ratio * 100, 1)}% of records are exact duplicates -- above the "
            f"{NOT_READY_DUPLICATE_RATIO * 100:.0f}% Not-Ready threshold"
        )
    if blockers:
        return {"status": "Not Ready", "reasons": blockers, "clean_ratio": clean_ratio, "duplicate_ratio": round(duplicate_ratio, 3)}

    improvements: list[str] = []
    if clean_ratio < READY_CLEAN_RATIO:
        improvements.append(f"clean_ratio {clean_ratio} is below the {READY_CLEAN_RATIO} Ready threshold")
    if duplicate_ratio > READY_DUPLICATE_RATIO:
        improvements.append(
            f"{round(duplicate_ratio * 100, 1)}% duplicate records -- above the "
            f"{READY_DUPLICATE_RATIO * 100:.0f}% Ready threshold"
        )
    if improvements:
        return {"status": "Needs Improvement", "reasons": improvements, "clean_ratio": clean_ratio, "duplicate_ratio": round(duplicate_ratio, 3)}

    return {
        "status": "Ready",
        "reasons": [
            f"clean_ratio {clean_ratio} >= {READY_CLEAN_RATIO}",
            f"duplicate ratio {round(duplicate_ratio * 100, 1)}% <= {READY_DUPLICATE_RATIO * 100:.0f}%",
            f"{record_count} records >= {MIN_RECORDS_FOR_TRAINING}-record minimum",
        ],
        "clean_ratio": clean_ratio, "duplicate_ratio": round(duplicate_ratio, 3),
    }
