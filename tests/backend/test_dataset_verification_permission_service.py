from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_verification_evidence_service import (
    ExternalDatasetEvidenceService,
    ExternalDatasetLicenceService,
)
from backend.services.dataset_verification_permission_service import (
    DatasetVerificationPermissionError,
    ExternalDatasetPermissionAssessmentService,
    ExternalDatasetUpstreamReviewService,
)
from core_model.data_verification import ADMIN_ONLY_PERMISSION_STATUSES, PERMISSION_TYPES

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "verification.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _create_case(settings: Settings, *, candidate_overrides: dict | None = None) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate_values = {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"}
    candidate_values.update(candidate_overrides or {})
    candidate = discovery.create_candidate(session["public_id"], candidate_values)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    return repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def _verify_cc_by_licence(settings: Settings, case_public_id: str) -> None:
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case_public_id,
        evidence_type="licence_file",
        content_text="Licensed under CC-BY-4.0.",
        admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case_public_id, admin_public_id=ADMIN_ID)


# -- ExternalDatasetPermissionAssessmentService.assess() -----------------------


def test_assess_covers_all_dimensions_except_commercial_use(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert set(results) == set(PERMISSION_TYPES) - {"commercial_use"}


def test_assess_never_produces_an_admin_only_status(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    for assessment in results.values():
        assert assessment["status"] not in ADMIN_ONLY_PERMISSION_STATUSES


def test_assess_training_use_never_reaches_likely_allowed_even_with_verified_licence(
    settings: Settings,
) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["training_use"]["status"] == "needs_legal_review"


def test_assess_rag_and_evaluation_use_reach_likely_allowed_on_verified_permissive_licence(
    settings: Settings,
) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["rag_use"]["status"] == "likely_allowed"
    assert results["evaluation_use"]["status"] == "likely_allowed"


def test_assess_with_no_licence_evidence_stays_unknown(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["training_use"]["status"] == "unknown"
    assert results["rag_use"]["status"] == "unknown"


def test_assess_capped_at_needs_legal_review_while_upstream_unresolved(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    upstream_service = ExternalDatasetUpstreamReviewService(settings)
    upstream_service.add_upstream_source(
        case["public_id"],
        {"candidate_public_id": case["candidate_public_id"], "upstream_name": "Common Voice"},
        admin_public_id=ADMIN_ID,
    )
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["rag_use"]["status"] == "needs_legal_review"
    assert results["evaluation_use"]["status"] == "needs_legal_review"


def test_assess_gated_access_derived_from_candidate_gated_flag(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"gated": True})
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["gated_access_restriction"]["status"] == "likely_restricted"


def test_assess_personal_data_restriction_from_privacy_evidence(settings: Settings) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="privacy_policy",
        content_text="This dataset contains personal data and requires informed consent.",
        admin_public_id=ADMIN_ID,
    )
    service = ExternalDatasetPermissionAssessmentService(settings)
    results = service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert results["personal_data_restriction"]["status"] == "likely_restricted"


def test_assess_permission_status_rollup_transitions(settings: Settings) -> None:
    case = _create_case(settings)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["permission_status"] == "not_started"

    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    service.assess_commercial_use(
        case["public_id"], intended_use_category="research", admin_public_id=ADMIN_ID
    )
    assert repository.get_case(case["public_id"])["permission_status"] == "incomplete"


# -- ExternalDatasetPermissionAssessmentService.assess_commercial_use() --------


def test_assess_commercial_use_never_reaches_likely_allowed(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    for category in (
        "internal_testing", "research", "free_public_service",
        "paid_commercial_product", "redistributed_dataset", "commercial_training_deployment",
    ):
        result = service.assess_commercial_use(
            case["public_id"], intended_use_category=category, admin_public_id=ADMIN_ID
        )
        assert result["status"] != "likely_allowed"
        assert result["conditions"]["intended_use_category"] == category


def test_assess_commercial_use_rejects_unknown_category(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetPermissionAssessmentService(settings)
    with pytest.raises(DatasetVerificationPermissionError):
        service.assess_commercial_use(
            case["public_id"], intended_use_category="not_a_real_category", admin_public_id=ADMIN_ID
        )


def test_assess_commercial_use_detects_non_commercial_evidence_text(settings: Settings) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="licence_file",
        content_text="This work is licensed for non-commercial use only.",
        admin_public_id=ADMIN_ID,
    )
    service = ExternalDatasetPermissionAssessmentService(settings)
    result = service.assess_commercial_use(
        case["public_id"], intended_use_category="paid_commercial_product", admin_public_id=ADMIN_ID
    )
    assert result["status"] == "likely_restricted"


# -- ExternalDatasetPermissionAssessmentService.review() -----------------------


def test_review_sets_admin_only_status_and_updates_rollup(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    service.assess(case["public_id"], admin_public_id=ADMIN_ID)

    reviewed = service.review(
        case["public_id"],
        "rag_use",
        status="approved",
        reviewed_by=REVIEWER_ID,
        reason="Licence file confirms CC-BY-4.0 permits RAG use",
    )
    assert reviewed["status"] == "approved"
    assert reviewed["reviewed_by"] == REVIEWER_ID

    reviews = service.repository.list_reviews(case["public_id"])
    assert any(r["decision"] == "approved" for r in reviews)


def test_review_requires_prior_automated_assessment(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetPermissionAssessmentService(settings)
    with pytest.raises(NotFoundError):
        service.review(
            case["public_id"],
            "rag_use",
            status="approved",
            reviewed_by=REVIEWER_ID,
            reason="No prior assessment exists",
        )


def test_review_rejects_non_admin_only_status(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_cc_by_licence(settings, case["public_id"])
    service = ExternalDatasetPermissionAssessmentService(settings)
    service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    with pytest.raises(ValidationError):
        service.review(
            case["public_id"],
            "rag_use",
            status="likely_allowed",
            reviewed_by=REVIEWER_ID,
            reason="not an admin-only status",
        )


# -- ExternalDatasetUpstreamReviewService ---------------------------------------


def test_add_upstream_source_marks_case_upstream_incomplete(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetUpstreamReviewService(settings)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["upstream_status"] == "not_started"

    service.add_upstream_source(
        case["public_id"],
        {"candidate_public_id": case["candidate_public_id"], "upstream_name": "Common Voice"},
        admin_public_id=ADMIN_ID,
    )
    assert repository.get_case(case["public_id"])["upstream_status"] == "incomplete"
    assert service.unresolved_upstream_exists(case["public_id"]) is True


def test_verify_upstream_source_marks_case_upstream_complete(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetUpstreamReviewService(settings)
    upstream = service.add_upstream_source(
        case["public_id"],
        {"candidate_public_id": case["candidate_public_id"], "upstream_name": "Common Voice"},
        admin_public_id=ADMIN_ID,
    )
    service.verify_upstream_source(
        case["public_id"],
        upstream["public_id"],
        verification_status="verified",
        admin_public_id=ADMIN_ID,
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["upstream_status"] == "complete"
    assert service.unresolved_upstream_exists(case["public_id"]) is False


def test_verify_upstream_source_rejects_unknown_status(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetUpstreamReviewService(settings)
    upstream = service.add_upstream_source(
        case["public_id"],
        {"candidate_public_id": case["candidate_public_id"], "upstream_name": "Common Voice"},
        admin_public_id=ADMIN_ID,
    )
    with pytest.raises(DatasetVerificationPermissionError):
        service.verify_upstream_source(
            case["public_id"],
            upstream["public_id"],
            verification_status="not_a_real_status",
            admin_public_id=ADMIN_ID,
        )


def test_upstream_conflicting_status_rolls_up_to_case(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetUpstreamReviewService(settings)
    upstream = service.add_upstream_source(
        case["public_id"],
        {"candidate_public_id": case["candidate_public_id"], "upstream_name": "Common Voice"},
        admin_public_id=ADMIN_ID,
    )
    service.verify_upstream_source(
        case["public_id"],
        upstream["public_id"],
        verification_status="conflicting",
        admin_public_id=ADMIN_ID,
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["upstream_status"] == "conflicting"
