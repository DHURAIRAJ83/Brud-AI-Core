"""Checkpoint retention classification shared by preview and apply.

Retention never deletes anything directly here; it only classifies each
checkpoint as ``protected`` (must never be removed) or ``eligible`` (may be
archived). Applying that classification is the caller's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROTECTED = "protected"
ELIGIBLE = "eligible"


@dataclass(frozen=True)
class RetentionPolicy:
    keep_periodic: int
    keep_best: int
    keep_final: int
    keep_pause: int


def classify(
    checkpoints: list[dict[str, Any]],
    policy: RetentionPolicy,
    *,
    promoted_checkpoint_public_ids: frozenset[str] = frozenset(),
    active_recovery_checkpoint_public_id: str | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(checkpoints, key=lambda row: (row["step"], row["created_at"]), reverse=True)
    keep_limits = {
        "periodic": policy.keep_periodic,
        "best_validation": policy.keep_best,
        "final": policy.keep_final,
        "pause": policy.keep_pause,
    }
    kept_counts = dict.fromkeys(keep_limits, 0)
    results: list[dict[str, Any]] = []
    for row in ordered:
        public_id = row["public_id"]
        reason: str | None = None
        if row.get("is_latest"):
            reason = "latest_verified_checkpoint"
        elif row.get("is_best"):
            reason = "best_validation_checkpoint"
        elif public_id in promoted_checkpoint_public_ids:
            reason = "promoted_checkpoint"
        elif (
            active_recovery_checkpoint_public_id
            and public_id == active_recovery_checkpoint_public_id
        ):
            reason = "active_recovery_checkpoint"
        elif row.get("checkpoint_kind") == "final":
            reason = "final_checkpoint"
        if reason:
            results.append(
                {"public_id": public_id, "classification": PROTECTED, "protection_reason": reason}
            )
            continue
        bucket = row.get("checkpoint_kind", "periodic")
        if bucket not in keep_limits:
            bucket = "periodic"
        if kept_counts[bucket] < keep_limits[bucket]:
            kept_counts[bucket] += 1
            results.append(
                {
                    "public_id": public_id,
                    "classification": PROTECTED,
                    "protection_reason": f"retained_{bucket}",
                }
            )
        else:
            results.append(
                {"public_id": public_id, "classification": ELIGIBLE, "protection_reason": None}
            )
    return results
