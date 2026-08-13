"""MB-07: Rollback Manager -- pure decision layer only. Decides
whether a requested rollback target is valid. The actual rollback
state machine (draft -> validated -> approved -> executed) is NOT
reimplemented here -- it is the existing `ModelReleaseService`'s own
`create_rollback_plan`/`validate_rollback_plan`/`approve_rollback_plan`/
`execute_rollback_plan` methods, already real and already tested. This
module only decides, ahead of calling those, whether the requested
target makes sense at all.
"""

from __future__ import annotations

from typing import Any

INELIGIBLE_STATUSES = {"archived", "retired"}


def evaluate_rollback_target(
    *, target_version: str, current_version: str | None, releases: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    target = next((r for r in releases if r.get("version") == target_version), None)

    if target is None:
        reasons.append(f"no release with version {target_version!r} exists for this family")
        return {"valid": False, "reasons": reasons, "target": None}

    if target_version == current_version:
        reasons.append("target version is already the current version -- nothing to roll back to")

    status = target.get("status")
    if status in INELIGIBLE_STATUSES:
        reasons.append(f"target release status is {status!r} -- {', '.join(sorted(INELIGIBLE_STATUSES))} releases are not valid rollback targets")

    return {"valid": not reasons, "reasons": reasons, "target": target}
