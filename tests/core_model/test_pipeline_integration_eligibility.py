from __future__ import annotations

from core_model.pipeline_integration.eligibility import (
    decide_pipeline_eligibility,
    is_legacy_record,
)


def _allowed():
    return {
        "decision": "allowed",
        "decision_code": "ALLOWED",
        "warnings": [],
        "required_actions": [],
    }


def _blocked(code="BLOCKED_QUALITY_ISSUE"):
    return {
        "decision": "blocked",
        "decision_code": code,
        "blocking_issue_ids": ["iss-1"],
        "warnings": [],
    }


def test_is_legacy_record_only_when_zero_governance_activity():
    assert is_legacy_record(has_review_item=False, has_any_target_approval=False) is True
    assert is_legacy_record(has_review_item=True, has_any_target_approval=False) is False
    assert is_legacy_record(has_review_item=False, has_any_target_approval=True) is False


def test_legacy_without_override_is_blocked():
    result = decide_pipeline_eligibility(
        target_pipeline="pretraining",
        governance_decision=_allowed(),
        is_legacy=True,
    )
    assert result["decision"] == "blocked"
    assert result["is_legacy"] is True
    assert result["decision_code"] == "LEGACY_UNCLASSIFIED"


def test_legacy_with_override_reason_is_eligible_with_a_warning():
    result = decide_pipeline_eligibility(
        target_pipeline="pretraining",
        governance_decision=_allowed(),
        is_legacy=True,
        legacy_override_reason="historical import, manually reviewed offline",
    )
    assert result["decision"] == "eligible"
    assert any("legacy override" in w for w in result["warnings"])


def test_governance_block_is_never_overridden_by_legacy_override():
    result = decide_pipeline_eligibility(
        target_pipeline="training",
        governance_decision=_blocked(),
        is_legacy=True,
        legacy_override_reason="some reason",
    )
    assert result["decision"] == "blocked"
    assert result["decision_code"] == "BLOCKED_QUALITY_ISSUE"


def test_needs_review_blocks_the_pipeline():
    result = decide_pipeline_eligibility(
        target_pipeline="rag",
        governance_decision={"decision": "needs_review", "decision_code": "REVIEW_IN_PROGRESS"},
        is_legacy=False,
    )
    assert result["decision"] == "blocked"


def test_already_exported_for_target_is_excluded_not_blocked():
    result = decide_pipeline_eligibility(
        target_pipeline="dataset_version",
        governance_decision=_allowed(),
        is_legacy=False,
        already_exported_for_target=True,
    )
    assert result["decision"] == "excluded"
    assert result["decision_code"] == "ALREADY_EXPORTED_FOR_TARGET"


def test_evaluation_isolation_excludes_regardless_of_governance_decision():
    result = decide_pipeline_eligibility(
        target_pipeline="pretraining",
        governance_decision=_allowed(),
        is_legacy=False,
        excluded_by_evaluation_isolation=True,
    )
    assert result["decision"] == "excluded"
    assert result["decision_code"] == "EVALUATION_ISOLATION"


def test_clean_allowed_record_is_eligible():
    result = decide_pipeline_eligibility(
        target_pipeline="rag", governance_decision=_allowed(), is_legacy=False
    )
    assert result["decision"] == "eligible"
    assert result["blocking_reasons"] == []
