import pytest

from core_model.semantic_chunk.lifecycle import (
    validate_chunk_transition,
    validate_structured_record_transition,
)


def test_draft_to_needs_review_is_valid():
    validate_chunk_transition("draft", "needs_review")


def test_draft_to_approved_is_invalid():
    with pytest.raises(ValueError, match="cannot transition"):
        validate_chunk_transition("draft", "approved")


def test_approved_to_needs_review_is_the_correction_pathway():
    validate_chunk_transition("approved", "needs_review")


def test_approved_cannot_go_directly_to_rejected():
    with pytest.raises(ValueError):
        validate_chunk_transition("approved", "rejected")


def test_self_transition_is_always_a_valid_no_op():
    for status in (
        "draft",
        "needs_review",
        "needs_structure_review",
        "needs_content_review",
        "approved",
        "rejected",
        "excluded",
        "archived",
    ):
        validate_chunk_transition(status, status)


def test_structured_record_draft_to_needs_review():
    validate_structured_record_transition("draft", "needs_review")


def test_structured_record_draft_to_approved_is_invalid():
    with pytest.raises(ValueError):
        validate_structured_record_transition("draft", "approved")


def test_structured_record_approved_to_needs_review_is_correction_pathway():
    validate_structured_record_transition("approved", "needs_review")
