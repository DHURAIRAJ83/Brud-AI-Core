"""MB-22: Checkpoint Namer -- pure. Deterministic naming, no-overwrite
enforcement, and a latest-checkpoint lookup helper. The database's own
unique index on (job_id, checkpoint_name) is the final authority
against a real overwrite race -- this module's own check is a fast,
honest pre-check, not a substitute for that constraint.
"""

from __future__ import annotations

from typing import Any


def build_checkpoint_name(*, step: int, epoch: int) -> str:
    return f"checkpoint-epoch{epoch:03d}-step{step:08d}"


def check_no_overwrite(*, checkpoint_name: str, existing_checkpoint_names: list[str]) -> dict[str, Any]:
    exists = checkpoint_name in existing_checkpoint_names
    return {
        "checkpoint_name": checkpoint_name, "already_exists": exists, "safe_to_write": not exists,
        "disclosure": "an existing checkpoint is never overwritten -- the database's own unique index on (job_id, checkpoint_name) is the final authority",
    }


def find_latest_checkpoint(*, checkpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not checkpoints:
        return None
    return max(checkpoints, key=lambda c: (c["step"], c["epoch"]))
