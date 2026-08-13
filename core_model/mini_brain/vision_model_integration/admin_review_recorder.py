"""MB-15: Admin Review -- pure. Validates one of the task's own ten
named review actions (approve, reject, rename, split, merge, delete,
add, move_box, resize_box, rotate_box) against a prediction's current
state before the service writes anything. Every action is recorded,
including reject and delete (both soft status flips, never row
deletes, so nothing is lost -- the same discipline MB-14's own
annotation recorder uses).
"""

from __future__ import annotations

from typing import Any

ACTIONS = (
    "approve", "reject", "rename", "split", "merge", "delete", "add", "move_box", "resize_box",
    "rotate_box",
)
_REQUIRES_EXISTING_PREDICTION = frozenset({
    "approve", "reject", "rename", "split", "delete", "move_box", "resize_box", "rotate_box",
})
_IS_CORRECTION = frozenset({"reject", "rename", "split", "merge", "delete", "move_box", "resize_box", "rotate_box"})


def record_review(
    *, action: str, current_prediction: dict[str, Any] | None, payload: dict[str, Any],
) -> dict[str, Any]:
    if action not in ACTIONS:
        return {"allowed": False, "reason": f"unknown action '{action}' -- must be one of {list(ACTIONS)}"}

    if action in _REQUIRES_EXISTING_PREDICTION and current_prediction is None:
        return {"allowed": False, "reason": f"action '{action}' requires an existing prediction"}

    if action in ("rename", "add") and not (payload.get("label") or "").strip():
        return {"allowed": False, "reason": f"'{action}' requires a non-empty label"}
    if action == "add" and not (payload.get("image_public_id") or "").strip():
        return {"allowed": False, "reason": "'add' requires an image_public_id"}
    if action in ("move_box", "resize_box", "rotate_box") and payload.get("bounding_box") is None:
        return {"allowed": False, "reason": f"'{action}' requires a bounding_box"}
    if action == "split":
        new_predictions = payload.get("new_predictions") or []
        if len(new_predictions) < 2:
            return {"allowed": False, "reason": "'split' requires at least 2 new_predictions"}
        for entry in new_predictions:
            if not (entry.get("label") or "").strip() or entry.get("bounding_box") is None:
                return {"allowed": False, "reason": "each split entry requires a label and a bounding_box"}
    if action == "merge":
        source_ids = payload.get("source_prediction_public_ids") or []
        if len(source_ids) < 2:
            return {"allowed": False, "reason": "'merge' requires at least 2 source_prediction_public_ids"}
        if not (payload.get("label") or "").strip() or payload.get("bounding_box") is None:
            return {"allowed": False, "reason": "'merge' requires a label and a bounding_box for the merged object"}

    return {
        "allowed": True, "action": action, "payload": payload, "is_correction": action in _IS_CORRECTION,
    }
