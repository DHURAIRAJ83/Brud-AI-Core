from __future__ import annotations

from core_model.data_governance.review import (
    GOVERNANCE_ENTITY_TYPES,
    GOVERNANCE_TARGET_USES,
    ISSUE_CATEGORIES,
    blocking_issue_ids_for_target,
    compute_review_priority,
)


def _issue(**overrides):
    base = {
        "issue_code": "X1",
        "issue_category": "language_quality",
        "severity": "warning",
        "is_blocking": False,
        "blocking_targets": [],
        "message": "msg",
        "public_id": "iss-1",
    }
    base.update(overrides)
    return base


def test_governance_entity_types_are_the_six_scoped_entities():
    assert GOVERNANCE_ENTITY_TYPES == (
        "document_page",
        "manual_data_record",
        "semantic_chunk",
        "structured_record_candidate",
        "document_candidate",
        "dataset_record",
    )
    assert "rag_candidate" not in GOVERNANCE_ENTITY_TYPES


def test_governance_target_uses_include_export_and_rag_handoff():
    assert "dataset_export" in GOVERNANCE_TARGET_USES
    assert "rag_handoff" in GOVERNANCE_TARGET_USES


def test_priority_is_urgent_for_a_critical_blocking_issue():
    issues = [_issue(severity="critical", is_blocking=True)]
    assert compute_review_priority(issues) == "urgent"


def test_priority_is_urgent_for_any_blocking_issue_on_a_high_risk_entity():
    issues = [_issue(severity="error", is_blocking=True)]
    assert compute_review_priority(issues, is_high_risk=True) == "urgent"


def test_priority_is_high_for_a_blocking_issue_on_a_normal_risk_entity():
    issues = [_issue(severity="error", is_blocking=True)]
    assert compute_review_priority(issues, is_high_risk=False) == "high"


def test_priority_is_normal_for_a_non_blocking_error_or_warning():
    assert compute_review_priority([_issue(severity="error", is_blocking=False)]) == "normal"
    assert compute_review_priority([_issue(severity="warning", is_blocking=False)]) == "normal"


def test_priority_is_low_with_only_info_or_no_issues():
    assert compute_review_priority([]) == "low"
    assert compute_review_priority([_issue(severity="info", is_blocking=False)]) == "low"


def test_blocking_issue_ids_for_target_respects_blocking_targets_scope():
    issues = [
        _issue(public_id="iss-a", is_blocking=True, blocking_targets=["training"]),
        _issue(public_id="iss-b", is_blocking=True, blocking_targets=[]),
        _issue(public_id="iss-c", is_blocking=False),
    ]
    assert blocking_issue_ids_for_target(issues, "training") == ["iss-a", "iss-b"]
    assert blocking_issue_ids_for_target(issues, "rag") == ["iss-b"]


def test_issue_categories_are_stable_and_match_schema_check_constraint():
    assert len(ISSUE_CATEGORIES) == 20
    assert len(set(ISSUE_CATEGORIES)) == 20
