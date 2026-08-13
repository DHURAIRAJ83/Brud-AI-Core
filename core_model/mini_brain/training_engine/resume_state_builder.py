"""MB-22: Resume State Builder -- pure. Builds the state a resumed job
needs from an already-fetched latest checkpoint and the last recorded
metric point -- resume must always reference a real, existing
checkpoint, never an assumed or synthetic one.
"""

from __future__ import annotations

from typing import Any


def build_resume_state(
    *, latest_checkpoint: dict[str, Any] | None, last_metric: dict[str, Any] | None,
) -> dict[str, Any]:
    if latest_checkpoint is None:
        return {
            "can_resume": False, "reason": "no existing checkpoint to resume from",
            "resume_step": 0, "resume_epoch": 0, "checkpoint_public_id": None,
        }
    return {
        "can_resume": True, "reason": None,
        "resume_step": latest_checkpoint["step"], "resume_epoch": latest_checkpoint["epoch"],
        "checkpoint_public_id": latest_checkpoint["public_id"],
        "checkpoint_name": latest_checkpoint["checkpoint_name"],
        "last_recorded_loss": last_metric["loss"] if last_metric else None,
        "disclosure": "resume always references a real, already-persisted checkpoint row -- never a synthetic or assumed state",
    }
