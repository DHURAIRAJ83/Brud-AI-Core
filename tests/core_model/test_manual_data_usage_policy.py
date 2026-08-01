import pytest

from core_model.manual_data.usage_policy import evaluate_manual_record_usage

ALLOWING_RIGHTS = {
    "rights_status": "licensed",
    "verification_status": "document_verified",
    "rag_use_allowed": True,
    "training_use_allowed": True,
    "evaluation_use_allowed": True,
    "commercial_use_allowed": True,
    "public_export_allowed": True,
    "redistribution_allowed": True,
}


def _source(**overrides):
    base = {"status": "verified", "source_type": "human_created"}
    base.update(overrides)
    return base


def _record(**overrides):
    base = {
        "status": "approved",
        "creation_method": "human_created",
        "fact_dependency": "none",
        "knowledge_risk": "language_only",
    }
    base.update(overrides)
    return base


def test_unsupported_target_use_raises():
    with pytest.raises(ValueError):
        evaluate_manual_record_usage(
            record=_record(),
            source=_source(),
            rights=ALLOWING_RIGHTS,
            verifications=[],
            target_use="not_a_use",
        )


def test_rejected_record_blocks_every_use():
    decision = evaluate_manual_record_usage(
        record=_record(status="rejected"),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[],
        target_use="rag",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] == "BLOCKED_RECORD_REJECTED"


def test_draft_record_blocked_for_training_but_not_reasoned_for_rag():
    decision = evaluate_manual_record_usage(
        record=_record(status="draft"),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[],
        target_use="training",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] == "BLOCKED_RECORD_NOT_APPROVED"


def test_ai_assisted_unreviewed_blocks_training():
    decision = evaluate_manual_record_usage(
        record=_record(status="needs_review", creation_method="ai_assisted"),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[],
        target_use="training",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] in (
        "BLOCKED_RECORD_NOT_APPROVED",
        "BLOCKED_AI_ASSISTED_UNREVIEWED",
    )


def test_high_risk_unverified_blocks_training():
    decision = evaluate_manual_record_usage(
        record=_record(knowledge_risk="high_risk", fact_dependency="high"),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[],
        target_use="training",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] == "BLOCKED_HIGH_RISK_UNVERIFIED"


def test_high_risk_verified_and_rights_allow_is_allowed():
    decision = evaluate_manual_record_usage(
        record=_record(knowledge_risk="high_risk", fact_dependency="high"),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[{"verification_status": "verified"}],
        target_use="training",
    )
    assert decision["allowed"] is True
    assert decision["decision_code"] == "ALLOWED"


def test_approved_record_still_blocked_when_rights_unknown():
    decision = evaluate_manual_record_usage(
        record=_record(),
        source=_source(),
        rights=None,
        verifications=[],
        target_use="training",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"


def test_approved_human_created_language_data_allowed_for_rag():
    decision = evaluate_manual_record_usage(
        record=_record(),
        source=_source(),
        rights=ALLOWING_RIGHTS,
        verifications=[],
        target_use="rag",
    )
    assert decision["allowed"] is True


def test_public_export_blocked_when_rights_disallow():
    rights = {**ALLOWING_RIGHTS, "public_export_allowed": False}
    decision = evaluate_manual_record_usage(
        record=_record(),
        source=_source(),
        rights=rights,
        verifications=[],
        target_use="public_export",
    )
    assert decision["allowed"] is False
    assert decision["decision_code"] == "BLOCKED_PUBLIC_EXPORT_NOT_ALLOWED"
