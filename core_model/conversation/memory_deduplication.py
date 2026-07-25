"""Memory duplicate and conflict detection.

Never silently chooses one conflicting memory -- returns an explicit
conflict status so the caller (service layer) can apply the retrieval
profile's configured ``conflict_policy`` or require confirmation.
"""

from __future__ import annotations

from typing import Any


def assess_conflict(
    *,
    proposed_normalized_value: str,
    existing_active_items: list[dict[str, Any]],
    category: str,
    purpose: str,
) -> dict[str, Any]:
    """``existing_active_items`` are other active memory items for the
    same participant scope. Returns one of the five conflict statuses
    plus the conflicting item's public_id, if any."""

    same_channel = [
        item
        for item in existing_active_items
        if item["category"] == category and item["purpose"] == purpose
    ]
    for item in same_channel:
        if item["normalized_value"] == proposed_normalized_value:
            return {
                "status": "duplicate",
                "conflicting_item_public_id": item["public_id"],
            }
    if same_channel:
        most_recent = max(same_channel, key=lambda item: item["created_at"])
        if most_recent["confidence_type"] == "user_confirmed":
            return {
                "status": "conflict_requires_confirmation",
                "conflicting_item_public_id": most_recent["public_id"],
            }
        return {
            "status": "supersedes_existing",
            "conflicting_item_public_id": most_recent["public_id"],
        }
    return {"status": "no_conflict", "conflicting_item_public_id": None}


def is_stale(*, created_epoch: float, ttl_seconds: int, now_epoch: float) -> bool:
    return (now_epoch - created_epoch) > ttl_seconds
