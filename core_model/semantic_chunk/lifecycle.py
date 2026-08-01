"""Semantic chunk and structured record candidate lifecycle transitions
(Phase 5, Step 3). Mirrors the shape of `core_model.manual_data.lifecycle`
and `core_model.document_workspace.lifecycle`: a plain dict of allowed
next states, checked before every status change.
"""

from __future__ import annotations

CHUNK_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"needs_review", "excluded", "archived"}),
    "needs_review": frozenset(
        {
            "needs_structure_review",
            "needs_content_review",
            "approved",
            "rejected",
            "draft",
            "excluded",
            "archived",
        }
    ),
    "needs_structure_review": frozenset(
        {"needs_review", "needs_content_review", "approved", "rejected", "draft", "excluded"}
    ),
    "needs_content_review": frozenset(
        {"needs_review", "needs_structure_review", "approved", "rejected", "draft", "excluded"}
    ),
    # "approved" -> "needs_review" is the *correction* pathway only: it
    # fires when a new draft revision is created against an approved
    # chunk (editing text/boundaries), never a direct in-place edit.
    # The previously approved revision is preserved untouched.
    "approved": frozenset({"needs_review", "excluded", "archived"}),
    "rejected": frozenset({"draft", "needs_review", "archived"}),
    "excluded": frozenset({"draft"}),
    "archived": frozenset({"draft"}),
}

STRUCTURED_RECORD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"needs_review", "archived"}),
    "needs_review": frozenset({"approved", "rejected", "draft", "archived"}),
    "approved": frozenset({"needs_review", "archived"}),
    "rejected": frozenset({"draft", "archived"}),
    "archived": frozenset({"draft"}),
}


def can_transition(transitions: dict[str, frozenset[str]], current: str, target: str) -> bool:
    if current == target:
        return True
    return target in transitions.get(current, frozenset())


def validate_chunk_transition(current_status: str, target_status: str) -> None:
    if not can_transition(CHUNK_STATUS_TRANSITIONS, current_status, target_status):
        raise ValueError(
            f"cannot transition semantic chunk from '{current_status}' to '{target_status}'"
        )


def validate_structured_record_transition(current_status: str, target_status: str) -> None:
    if not can_transition(STRUCTURED_RECORD_STATUS_TRANSITIONS, current_status, target_status):
        raise ValueError(
            f"cannot transition structured record candidate from "
            f"'{current_status}' to '{target_status}'"
        )
