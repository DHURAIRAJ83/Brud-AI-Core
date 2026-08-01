"""Manual data record lifecycle transitions (Phase 3, Step 3).

Mirrors the shape of `backend.services.dataset_service.TRANSITIONS` and
Phase 2's `_SOURCE_STATUS_TRANSITIONS`: a plain dict of allowed next
states, checked before every status change so an invalid jump (e.g.
`draft` straight to `approved`) is rejected with a clear reason rather
than silently allowed.
"""

from __future__ import annotations

STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"needs_review", "archived"}),
    "needs_review": frozenset(
        {
            "needs_source_verification",
            "needs_domain_review",
            "approved",
            "rejected",
            "draft",
            "archived",
        }
    ),
    "needs_source_verification": frozenset(
        {"needs_review", "needs_domain_review", "approved", "rejected", "draft", "archived"}
    ),
    "needs_domain_review": frozenset(
        {"needs_review", "needs_source_verification", "approved", "rejected", "draft", "archived"}
    ),
    # "approved" -> "draft" is the *correction* pathway only (Step 3): it
    # fires when a new draft revision is created against an approved
    # record, never a direct in-place edit. The previously approved
    # revision row is preserved untouched in `manual_data_record_revisions`
    # and remains `active_revision_id` until the new revision is itself
    # approved.
    "approved": frozenset({"archived", "draft"}),
    "rejected": frozenset({"draft", "archived"}),
    "archived": frozenset({"draft"}),
}


def can_transition(current_status: str, target_status: str) -> bool:
    return target_status in STATUS_TRANSITIONS.get(current_status, frozenset())


def validate_transition(current_status: str, target_status: str) -> None:
    if not can_transition(current_status, target_status):
        raise ValueError(
            f"cannot transition manual data record from '{current_status}' to '{target_status}'"
        )
