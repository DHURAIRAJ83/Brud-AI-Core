"""Dataset-candidate licence and provenance evidence.

Every candidate must carry an explicit, honest licence/provenance
record -- unknown is never silently treated as approved.
"""

from __future__ import annotations

from typing import Any

_APPROVED_CREATOR_TYPES = frozenset({"admin_authored", "reviewer_corrected"})


def assess_provenance(
    *,
    feedback_source_type: str,
    content_creator_type: str,
    consent_status: str,
    declared_licence_status: str,
    reviewer_attribution_public_id: str | None,
    source_deleted: bool,
) -> dict[str, Any]:
    """Returns the licence status to record on the candidate plus
    whether provenance is complete enough to approve. ``unknown`` or
    ``blocked`` licence always blocks training-data approval regardless
    of every other check passing."""

    valid_licence_statuses = {"approved", "restricted", "unknown", "blocked", "not_applicable"}
    if declared_licence_status not in valid_licence_statuses:
        declared_licence_status = "unknown"

    complete = bool(feedback_source_type) and bool(content_creator_type) and bool(consent_status)
    if content_creator_type not in _APPROVED_CREATOR_TYPES and not reviewer_attribution_public_id:
        complete = False

    licence_status = declared_licence_status
    if source_deleted and licence_status == "approved":
        # The underlying feedback/session content was deleted; the
        # candidate's own reviewed text may still be retained (it no
        # longer contains the deleted source content), but the licence
        # decision must be re-confirmed by a human, not assumed to
        # still hold automatically.
        licence_status = "restricted"

    blocks_approval = licence_status in {"unknown", "blocked"} or not complete

    return {
        "licence_status": licence_status,
        "provenance_complete": complete,
        "blocks_approval": blocks_approval,
        "source_deleted": source_deleted,
    }
