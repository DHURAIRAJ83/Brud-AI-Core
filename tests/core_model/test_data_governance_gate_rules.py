from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core_model.data_governance.gate_rules import evaluate_target_approval, is_approval_expired


def _issue(**overrides):
    base = {
        "public_id": "iss-1",
        "is_blocking": True,
        "blocking_targets": [],
        "severity": "critical",
        "issue_code": "X",
    }
    base.update(overrides)
    return base


def _allowed_usage():
    return {"allowed": True, "decision_code": "ALLOWED", "warnings": [], "required_actions": []}


def test_allowed_when_no_blockers_present():
    decision = evaluate_target_approval(
        target_use="rag",
        usage_decision=_allowed_usage(),
        normalized_issues=[],
    )
    assert decision["decision"] == "allowed"
    assert decision["decision_code"] == "ALLOWED"


def test_rights_block_takes_priority_and_is_never_overridden_by_quality():
    decision = evaluate_target_approval(
        target_use="training",
        usage_decision={
            "allowed": False,
            "decision_code": "BLOCKED_RIGHTS_UNKNOWN",
            "warnings": [],
            "required_actions": ["Declare rights."],
        },
        normalized_issues=[],
    )
    assert decision["decision"] == "blocked"
    assert decision["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"


def test_blocking_quality_issue_blocks_even_with_allowed_usage_decision():
    decision = evaluate_target_approval(
        target_use="training",
        usage_decision=_allowed_usage(),
        normalized_issues=[_issue(is_blocking=True, blocking_targets=["training"])],
    )
    assert decision["decision"] == "blocked"
    assert decision["decision_code"] == "BLOCKED_QUALITY_ISSUE"
    assert decision["blocking_issue_ids"] == ["iss-1"]


def test_blocking_issue_scoped_to_other_target_does_not_block_this_one():
    decision = evaluate_target_approval(
        target_use="rag",
        usage_decision=_allowed_usage(),
        normalized_issues=[_issue(is_blocking=True, blocking_targets=["training"])],
    )
    assert decision["decision"] == "allowed"


def test_open_duplicate_group_blocks_regardless_of_quality():
    decision = evaluate_target_approval(
        target_use="dataset_export",
        usage_decision=None,
        normalized_issues=[],
        open_duplicate_group=True,
    )
    assert decision["decision"] == "blocked"
    assert decision["decision_code"] == "BLOCKED_UNRESOLVED_DUPLICATE"


def test_open_conflict_group_blocks_regardless_of_quality():
    decision = evaluate_target_approval(
        target_use="dataset_export",
        usage_decision=None,
        normalized_issues=[],
        open_conflict_group=True,
    )
    assert decision["decision"] == "blocked"
    assert decision["decision_code"] == "BLOCKED_UNRESOLVED_CONFLICT"


def test_open_review_item_yields_needs_review_when_otherwise_clear():
    decision = evaluate_target_approval(
        target_use="rag_handoff",
        usage_decision=None,
        normalized_issues=[],
        review_item_open=True,
    )
    assert decision["decision"] == "needs_review"
    assert decision["decision_code"] == "REVIEW_IN_PROGRESS"


def test_expiry_helper():
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert is_approval_expired(past) is True
    assert is_approval_expired(future) is False
    assert is_approval_expired(None) is False
