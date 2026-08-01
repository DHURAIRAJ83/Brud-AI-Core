import pytest

from core_model.document_workspace.lifecycle import can_transition, validate_transition


def test_pending_can_move_to_needs_correction_approved_rejected_excluded():
    for target in ("needs_correction", "approved", "rejected", "excluded"):
        assert can_transition("pending", target)


def test_pending_cannot_move_to_corrected_directly():
    assert not can_transition("pending", "corrected")
    with pytest.raises(ValueError):
        validate_transition("pending", "corrected")


def test_approved_only_allows_needs_correction():
    assert can_transition("approved", "needs_correction")
    assert not can_transition("approved", "rejected")
    assert not can_transition("approved", "pending")


def test_excluded_can_be_reopened_to_pending():
    assert can_transition("excluded", "pending")
    assert not can_transition("excluded", "approved")


def test_rejected_can_return_to_pending_or_needs_correction():
    assert can_transition("rejected", "pending")
    assert can_transition("rejected", "needs_correction")
    assert not can_transition("rejected", "approved")


def test_unknown_status_has_no_valid_transitions():
    assert not can_transition("not_a_real_status", "approved")


def test_self_transition_is_always_a_valid_no_op():
    # A rerun request targeting the current status (e.g. requesting an
    # OCR rerun on an already-`pending` page) must not be rejected as an
    # invalid transition just because nothing changes.
    for status in ("pending", "needs_correction", "corrected", "approved", "rejected", "excluded"):
        assert can_transition(status, status)
        validate_transition(status, status)
