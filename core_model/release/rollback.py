"""Metadata-level rollback planning and target eligibility.

Rollback in Phase 14 never touches running infrastructure, the public
chatbot assignment, or any file on disk — it only changes which release a
family's ``current_release_public_id`` points to, and records an
append-only rollback event. A rollback target must itself be verified and
eligible; rolling back to a corrupt or blocked release is rejected.
"""

from __future__ import annotations

from typing import Any


def assess_rollback_target(
    *,
    target_status: str,
    target_archived: bool,
    target_artifacts_verified: bool,
    target_manifest_verified: bool,
    target_family_compatible: bool,
    target_deployment_eligibility: str,
    target_evaluation_blocked: bool,
    target_has_blocking_issue: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if target_status not in {"released", "deprecated"}:
        reasons.append("target_not_previously_released")
    if target_archived:
        reasons.append("target_archived")
    if not target_artifacts_verified:
        reasons.append("target_artifacts_unverified")
    if not target_manifest_verified:
        reasons.append("target_manifest_unverified")
    if not target_family_compatible:
        reasons.append("target_incompatible_with_family")
    if target_deployment_eligibility == "not_deployable":
        reasons.append("target_not_deployable")
    if target_evaluation_blocked:
        reasons.append("target_evaluation_blocked")
    if target_has_blocking_issue:
        reasons.append("target_has_unresolved_blocking_issue")
    return {"eligible": not reasons, "reasons": reasons}


def build_rollback_event(
    *,
    previous_release_public_id: str,
    new_release_public_id: str,
    approval_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "previous_release_public_id": previous_release_public_id,
        "new_release_public_id": new_release_public_id,
        "approval_evidence": approval_evidence,
    }
