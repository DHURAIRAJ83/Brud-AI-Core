"""Page-level review lifecycle transitions (Phase 4, Step 2/19).

Deliberately separate from the existing `document_pages.extraction_status`
transitions (which are unchanged, inline in `document_service.py`) --
this governs human *review* outcome only. Mirrors the shape of
`core_model.manual_data.lifecycle` (a plain dict of allowed next
states, checked before every status change).
"""

from __future__ import annotations

STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"needs_correction", "approved", "rejected", "excluded"}),
    "needs_correction": frozenset({"corrected", "rejected", "excluded"}),
    "corrected": frozenset({"approved", "needs_correction", "rejected", "excluded"}),
    # "approved" -> "needs_correction" is the *correction* pathway only
    # (Step 9/19): it fires when a new draft revision is created against
    # an approved page, never a direct in-place edit. The previously
    # approved revision is preserved via `approved_revision_number` and
    # the immutable `document_page_revisions` history.
    "approved": frozenset({"needs_correction"}),
    "rejected": frozenset({"pending", "needs_correction"}),
    "excluded": frozenset({"pending"}),
}


def can_transition(current_status: str, target_status: str) -> bool:
    # A transition to the same status is always a legal no-op (e.g.
    # requesting an OCR rerun on an already-`pending` page must not be
    # treated as an invalid transition just because nothing changes).
    if current_status == target_status:
        return True
    return target_status in STATUS_TRANSITIONS.get(current_status, frozenset())


def validate_transition(current_status: str, target_status: str) -> None:
    if not can_transition(current_status, target_status):
        raise ValueError(
            f"cannot transition document page review from '{current_status}' to '{target_status}'"
        )
