"""MB-14: Admin Annotation -- pure. Validates one of the task's own
six named annotation actions (rename, delete, add, correct_caption,
correct_label, redraw_box) against the object's current state before
the service writes anything. Every action is recorded, including
delete (a soft status flip, never a row delete, so nothing is lost).
"""

from __future__ import annotations

from typing import Any

ACTIONS = ("rename", "delete", "add", "correct_caption", "correct_label", "redraw_box")
_REQUIRES_EXISTING_OBJECT = frozenset({"rename", "delete", "correct_caption", "correct_label", "redraw_box"})


def record_annotation(
    *, action: str, current_object: dict[str, Any] | None, payload: dict[str, Any],
) -> dict[str, Any]:
    if action not in ACTIONS:
        return {"allowed": False, "reason": f"unknown action '{action}' -- must be one of {list(ACTIONS)}"}

    if action in _REQUIRES_EXISTING_OBJECT and current_object is None:
        return {"allowed": False, "reason": f"action '{action}' requires an existing object"}

    if action == "add" and not (payload.get("label") or "").strip():
        return {"allowed": False, "reason": "'add' requires a non-empty label"}
    if action == "rename" and not (payload.get("label") or "").strip():
        return {"allowed": False, "reason": "'rename' requires a non-empty label"}
    if action == "redraw_box" and not payload.get("bounding_box"):
        return {"allowed": False, "reason": "'redraw_box' requires a bounding_box"}
    if action == "correct_caption" and not (payload.get("caption") or "").strip():
        return {"allowed": False, "reason": "'correct_caption' requires a non-empty caption"}

    return {"allowed": True, "action": action, "payload": payload}
