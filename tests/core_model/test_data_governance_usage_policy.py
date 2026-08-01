"""Matrix tests for the Phase 2 Source, Rights & Usage Registry policy
module. Every ``UsageDecision.decision_code`` the module can return is
exercised at least once."""

from __future__ import annotations

from core_model.data_governance.usage_policy import (
    evaluate_source_usage,
    rights_from_corpus_licence_row,
    validate_rights_combination,
)


def _source(**overrides):
    base = {
        "status": "verified",
        "source_type": "human_created",
        "independent_reviewer_required": False,
        "internal_rag_policy_allows_unknown_rights": False,
    }
    base.update(overrides)
    return base


def _rights(**overrides):
    base = {
        "rights_status": "licensed",
        "verification_status": "document_verified",
        "attribution_required": False,
        "attribution_text": None,
        "modification_allowed": True,
        "commercial_use_allowed": True,
        "rag_use_allowed": True,
        "training_use_allowed": True,
        "evaluation_use_allowed": True,
        "public_export_allowed": True,
        "redistribution_allowed": True,
        "internal_only": False,
    }
    base.update(overrides)
    return base


class TestSourceStatusGates:
    def test_rejected_source_blocks_every_use(self):
        source = _source(status="rejected")
        for target in (
            "rag",
            "training",
            "evaluation",
            "commercial",
            "public_export",
            "redistribution",
        ):
            decision = evaluate_source_usage(source=source, rights=_rights(), target_use=target)
            assert decision["allowed"] is False
            assert decision["decision_code"] == "BLOCKED_SOURCE_REJECTED"

    def test_archived_source_blocks_every_use(self):
        decision = evaluate_source_usage(
            source=_source(status="archived"), rights=_rights(), target_use="rag"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_SOURCE_REJECTED"

    def test_restricted_source_still_allows_rag_but_blocks_training(self):
        source = _source(status="restricted")
        rag = evaluate_source_usage(source=source, rights=_rights(), target_use="rag")
        training = evaluate_source_usage(source=source, rights=_rights(), target_use="training")
        assert rag["allowed"] is True
        assert training["allowed"] is False


class TestRightsUnknownFailsClosed:
    def test_no_rights_declaration_blocks_training_commercial_export(self):
        for target in ("training", "commercial", "public_export", "redistribution", "evaluation"):
            decision = evaluate_source_usage(source=_source(), rights=None, target_use=target)
            assert decision["allowed"] is False
            assert decision["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"

    def test_unknown_rights_blocks_rag_unless_explicit_internal_policy_allows_it(self):
        blocked = evaluate_source_usage(source=_source(), rights=None, target_use="rag")
        assert blocked["allowed"] is False
        assert blocked["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"

        allowed = evaluate_source_usage(
            source=_source(internal_rag_policy_allows_unknown_rights=True),
            rights=None,
            target_use="rag",
        )
        assert allowed["allowed"] is True
        assert allowed["decision_code"] == "REVIEW_REQUIRED_INTERNAL_RAG"
        assert allowed["warnings"]

    def test_pending_review_blocks_with_specific_code(self):
        decision = evaluate_source_usage(
            source=_source(), rights=_rights(rights_status="pending_review"), target_use="training"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_PERMISSION_PENDING"


class TestExpiredAndProhibited:
    def test_expired_rights_status_blocks(self):
        decision = evaluate_source_usage(
            source=_source(), rights=_rights(rights_status="expired"), target_use="rag"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_LICENSE_EXPIRED"

    def test_expired_permission_date_blocks_even_if_status_field_lags(self):
        decision = evaluate_source_usage(
            source=_source(), rights=_rights(permission_expired=True), target_use="training"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_LICENSE_EXPIRED"

    def test_prohibited_rights_status_blocks_everything(self):
        decision = evaluate_source_usage(
            source=_source(), rights=_rights(rights_status="prohibited"), target_use="rag"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_SOURCE_REJECTED"


class TestAiOriginRequiresHumanReview:
    def test_ai_generated_unverified_blocked_outside_rag(self):
        source = _source(source_type="ai_generated")
        decision = evaluate_source_usage(
            source=source,
            rights=_rights(verification_status="self_declared"),
            target_use="training",
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_VERIFICATION_REQUIRED"

    def test_ai_assisted_unverified_still_permitted_for_rag(self):
        source = _source(source_type="ai_assisted")
        decision = evaluate_source_usage(
            source=source, rights=_rights(verification_status="unverified"), target_use="rag"
        )
        assert decision["allowed"] is True

    def test_ai_generated_becomes_eligible_once_owner_confirmed(self):
        source = _source(source_type="ai_generated")
        decision = evaluate_source_usage(
            source=source,
            rights=_rights(verification_status="owner_confirmed"),
            target_use="training",
        )
        assert decision["allowed"] is True
        assert decision["decision_code"] == "ALLOWED"


class TestHighRiskFactualDataRequiresIndependentReview:
    def test_independent_reviewer_required_blocks_training_until_strongly_verified(self):
        source = _source(independent_reviewer_required=True)
        weak = evaluate_source_usage(
            source=source,
            rights=_rights(verification_status="self_declared"),
            target_use="training",
        )
        assert weak["allowed"] is False
        assert weak["decision_code"] == "BLOCKED_VERIFICATION_REQUIRED"

        strong = evaluate_source_usage(
            source=source,
            rights=_rights(verification_status="legal_reviewed"),
            target_use="training",
        )
        assert strong["allowed"] is True

    def test_independent_reviewer_required_does_not_block_rag(self):
        source = _source(independent_reviewer_required=True)
        decision = evaluate_source_usage(
            source=source, rights=_rights(verification_status="self_declared"), target_use="rag"
        )
        assert decision["allowed"] is True


class TestPerTargetFlags:
    def test_each_target_use_checks_its_own_flag(self):
        for target, flag in [
            ("rag", "rag_use_allowed"),
            ("training", "training_use_allowed"),
            ("evaluation", "evaluation_use_allowed"),
            ("commercial", "commercial_use_allowed"),
            ("public_export", "public_export_allowed"),
            ("redistribution", "redistribution_allowed"),
        ]:
            rights = _rights(**{flag: False})
            decision = evaluate_source_usage(source=_source(), rights=rights, target_use=target)
            assert decision["allowed"] is False, target
            assert decision["decision_code"].startswith("BLOCKED_")

    def test_internal_only_blocks_external_uses_even_if_flag_true(self):
        rights = _rights(internal_only=True)
        for target in ("public_export", "commercial", "redistribution"):
            decision = evaluate_source_usage(source=_source(), rights=rights, target_use=target)
            assert decision["allowed"] is False
        rag_decision = evaluate_source_usage(source=_source(), rights=rights, target_use="rag")
        assert rag_decision["allowed"] is True

    def test_public_export_without_attribution_text_warns_but_allows(self):
        rights = _rights(attribution_required=True, attribution_text=None)
        decision = evaluate_source_usage(
            source=_source(), rights=rights, target_use="public_export"
        )
        assert decision["allowed"] is True
        assert "attribution_required_but_no_attribution_text_set" in decision["warnings"]

    def test_commercial_without_strong_verification_warns_but_allows(self):
        rights = _rights(verification_status="self_declared")
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="commercial")
        assert decision["allowed"] is True
        assert decision["warnings"]

    def test_fully_allowed_returns_allowed_code_with_no_reasons(self):
        decision = evaluate_source_usage(source=_source(), rights=_rights(), target_use="training")
        assert decision == {
            "allowed": True,
            "decision_code": "ALLOWED",
            "blocking_reasons": [],
            "warnings": [],
            "required_actions": [],
        }

    def test_unsupported_target_use_raises(self):
        import pytest

        with pytest.raises(ValueError):
            evaluate_source_usage(source=_source(), rights=_rights(), target_use="not_a_real_use")


class TestCorpusLicenceAdapterMatrix:
    """Exercises the licence families named explicitly in the task's Step
    14 matrix, via the corpus-licence adapter feeding the same policy."""

    def test_public_domain_style_approved_licence_allows_training(self):
        row = {
            "licence_family": "public_domain",
            "review_status": "approved",
            "ai_training_permitted": True,
            "redistribution_permitted": True,
            "commercial_use_permitted": True,
            "modification_permitted": True,
            "attribution_required": False,
            "evidence_type": "document_evidence",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="training")
        assert decision["allowed"] is True

    def test_cc_by_conditional_approval_allows_with_attribution(self):
        row = {
            "licence_family": "cc_by",
            "review_status": "approved_with_conditions",
            "ai_training_permitted": True,
            "redistribution_permitted": True,
            "attribution_required": True,
            "copyright_holder": "Example Author",
            "evidence_type": "document_evidence",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(
            source=_source(), rights=rights, target_use="public_export"
        )
        assert decision["allowed"] is True

    def test_cc_by_sa_share_alike_still_evaluated_through_same_flags(self):
        row = {
            "licence_family": "cc_by_sa",
            "review_status": "approved_with_conditions",
            "ai_training_permitted": True,
            "redistribution_permitted": False,
            "evidence_type": "admin_asserted",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(
            source=_source(), rights=rights, target_use="redistribution"
        )
        assert decision["allowed"] is False

    def test_government_source_with_unknown_licence_fails_closed(self):
        row = {
            "licence_family": "unknown",
            "review_status": "unknown",
            "evidence_type": "admin_asserted",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(
            source=_source(source_type="government_source"), rights=rights, target_use="training"
        )
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"

    def test_research_only_licence_blocks_commercial_via_flag(self):
        row = {
            "licence_family": "research_only",
            "review_status": "approved_with_conditions",
            "ai_training_permitted": True,
            "commercial_use_permitted": False,
            "redistribution_permitted": False,
            "evidence_type": "admin_asserted",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="commercial")
        assert decision["allowed"] is False

    def test_non_commercial_licence_blocks_commercial(self):
        row = {
            "licence_family": "non_commercial",
            "review_status": "approved_with_conditions",
            "ai_training_permitted": True,
            "commercial_use_permitted": False,
            "evidence_type": "admin_asserted",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="commercial")
        assert decision["allowed"] is False

    def test_permission_granted_style_licence_via_owner_confirmation(self):
        row = {
            "licence_family": "user_owned_with_permission",
            "review_status": "approved",
            "ai_training_permitted": True,
            "redistribution_permitted": True,
            "commercial_use_permitted": True,
            "evidence_type": "owner_confirmation",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="commercial")
        assert decision["allowed"] is True

    def test_expired_corpus_licence_blocks_via_adapter(self):
        row = {
            "licence_family": "cc_by",
            "review_status": "approved",
            "ai_training_permitted": True,
            "expires_at": "2000-01-01T00:00:00+00:00",
            "evidence_type": "document_evidence",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="training")
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_LICENSE_EXPIRED"

    def test_prohibited_all_rights_reserved_blocks(self):
        row = {
            "licence_family": "all_rights_reserved",
            "review_status": "blocked",
            "evidence_type": "admin_asserted",
        }
        rights = rights_from_corpus_licence_row(row)
        decision = evaluate_source_usage(source=_source(), rights=rights, target_use="rag")
        assert decision["allowed"] is False


class TestValidateRightsCombination:
    def test_open_license_requires_identifier_or_name(self):
        errors = validate_rights_combination(
            _rights(rights_status="open_license", license_name=None, license_identifier=None)
        )
        assert any("open_license" in e for e in errors)

    def test_permission_granted_requires_reference(self):
        errors = validate_rights_combination(
            _rights(rights_status="permission_granted", permission_reference=None)
        )
        assert any("permission_granted" in e for e in errors)

    def test_public_export_requires_redistribution(self):
        errors = validate_rights_combination(
            _rights(public_export_allowed=True, redistribution_allowed=False)
        )
        assert any("public_export_allowed" in e for e in errors)

    def test_commercial_requires_strong_verification(self):
        errors = validate_rights_combination(
            _rights(commercial_use_allowed=True, verification_status="self_declared")
        )
        assert any("commercial_use_allowed" in e for e in errors)

    def test_training_allowed_cannot_coexist_with_unknown_rights_status(self):
        errors = validate_rights_combination(
            _rights(training_use_allowed=True, rights_status="unknown")
        )
        assert any("training_use_allowed" in e for e in errors)

    def test_fully_consistent_declaration_has_no_errors(self):
        assert validate_rights_combination(_rights()) == []
