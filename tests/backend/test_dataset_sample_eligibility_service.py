from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_data_providers import ExternalDataProviderRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_sample_eligibility_service import (
    DatasetSampleImportError,
    ExternalDatasetSampleApprovalService,
    ExternalDatasetSampleEligibilityService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "eligibility.db",
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
    candidate_values = {
        "canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus",
        "declared_licence": "CC-BY-4.0",
    }
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


def _finalize_case(
    settings: Settings,
    *,
    identity_status: str = "verified",
    rag_use_status: str | None = "approved",
    evaluation_use_status: str | None = "approved",
) -> dict:
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    case = _create_case(settings)
    repository.update_case(case["public_id"], {"identity_status": identity_status})
    for permission_type, status in (
        ("rag_use", rag_use_status), ("evaluation_use", evaluation_use_status),
    ):
        if status is None:
            continue
        repository.assess_permission(
            case["public_id"], permission_type,
            {"candidate_public_id": case["candidate_public_id"], "status": "likely_allowed"},
        )
        repository.review_permission(
            case["public_id"], permission_type,
            status=status, reviewed_by=ADMIN_ID, reason="Licence review",
        )
    return repository.lock_case(case["public_id"], {"summary": "finalized for test"})


def _create_provider(
    settings: Settings, *, enabled: bool = True, lifecycle_status: str = "enabled"
) -> str:
    repository = ExternalDataProviderRepository(settings.resolved_database_path)
    provider = repository.create_provider(
        {
            "provider_code": "prov-1",
            "name": "Example Provider",
            "provider_type": "dataset_catalogue",
            "access_mode": "public",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    repository.update_provider(
        provider["public_id"], {"enabled": int(enabled), "lifecycle_status": lifecycle_status}
    )
    return provider["public_id"]


# -- eligibility --------------------------------------------------------------------


def test_check_eligibility_blocks_when_case_not_finalized(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="manual_review")
    assert result["eligible"] is False
    assert any("finalized" in reason for reason in result["blocking_reasons"])


def test_check_eligibility_blocks_when_identity_not_verified(settings: Settings) -> None:
    case = _finalize_case(settings, identity_status="partial")
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="manual_review")
    assert result["eligible"] is False
    assert result["checks"]["identity_sufficiently_verified"]["passed"] is False


def test_check_eligibility_passes_for_finalized_verified_case(settings: Settings) -> None:
    case = _finalize_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(
        case["public_id"], purpose="rag_sandbox_preparation", dataset_version="v1", revision="r1"
    )
    assert result["eligible"] is True
    assert result["blocking_reasons"] == []


def test_check_eligibility_blocks_when_relevant_permission_prohibited(settings: Settings) -> None:
    case = _finalize_case(settings, rag_use_status="prohibited")
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="rag_sandbox_preparation")
    assert result["eligible"] is False
    assert result["checks"]["relevant_permission_eligible"]["passed"] is False


def test_check_eligibility_does_not_require_training_permission_for_rag_sandbox(
    settings: Settings,
) -> None:
    # Training permission was never assessed at all -- only rag_use was
    # -- and eligibility must still pass, per the spec's explicit
    # "training permission is not required merely to perform a
    # RAG-oriented sample inspection."
    case = _finalize_case(settings, evaluation_use_status=None)
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="rag_sandbox_preparation")
    assert result["eligible"] is True


def test_check_eligibility_blocks_on_active_withdrawal_notice(settings: Settings) -> None:
    case = _finalize_case(settings)
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    verification.record_withdrawal_notice(
        case["public_id"],
        {
            "candidate_public_id": case["candidate_public_id"],
            "notice_type": "licence_changed",
            "recorded_by_admin_public_id": ADMIN_ID,
        },
    )
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="manual_review")
    assert result["eligible"] is False
    assert result["checks"]["no_active_withdrawal_notice"]["passed"] is False


def test_check_eligibility_blocks_on_unresolved_upstream(settings: Settings) -> None:
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case_draft = _create_case(settings)
    verification.add_upstream_source(
        case_draft["public_id"],
        {
            "candidate_public_id": case_draft["candidate_public_id"],
            "upstream_name": "Some Upstream Corpus",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    verification.update_case(case_draft["public_id"], {"identity_status": "verified"})
    for permission_type in ("rag_use", "evaluation_use"):
        verification.assess_permission(
            case_draft["public_id"], permission_type,
            {"candidate_public_id": case_draft["candidate_public_id"], "status": "likely_allowed"},
        )
        verification.review_permission(
            case_draft["public_id"], permission_type,
            status="approved", reviewed_by=ADMIN_ID, reason="ok",
        )
    finalized = verification.lock_case(case_draft["public_id"], {"summary": "done"})

    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(finalized["public_id"], purpose="manual_review")
    assert result["eligible"] is False
    assert result["checks"]["upstream_blockers_resolved"]["passed"] is False


def test_check_eligibility_warns_but_does_not_block_when_version_unpinned(
    settings: Settings,
) -> None:
    case = _finalize_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(case["public_id"], purpose="manual_review")
    assert result["eligible"] is True
    assert any("reproducibility" in warning for warning in result["warnings"])


def test_check_eligibility_blocks_disabled_provider(settings: Settings) -> None:
    case = _finalize_case(settings)
    provider_id = _create_provider(settings, enabled=False, lifecycle_status="disabled")
    service = ExternalDatasetSampleEligibilityService(settings)
    result = service.check_eligibility(
        case["public_id"], purpose="manual_review", provider_public_id=provider_id
    )
    assert result["eligible"] is False
    assert result["checks"]["provider_enabled_and_not_blocked"]["passed"] is False


def test_check_eligibility_rejects_prohibited_purpose(settings: Settings) -> None:
    case = _finalize_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    with pytest.raises(DatasetSampleImportError):
        service.check_eligibility(case["public_id"], purpose="training")


def test_create_sample_import_raises_when_not_eligible(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    with pytest.raises(DatasetSampleImportError):
        service.create_sample_import(
            case["public_id"],
            {
                "purpose": "manual_review",
                "selection_method": "deterministic_first_n",
                "requested_by_admin_public_id": ADMIN_ID,
            },
        )


def test_create_sample_import_succeeds_and_records_event(settings: Settings) -> None:
    case = _finalize_case(settings)
    service = ExternalDatasetSampleEligibilityService(settings)
    sample_import = service.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 100,
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    assert sample_import["status"] == "draft"
    assert sample_import["verification_case_public_id"] == case["public_id"]

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    events = samples.list_events(sample_import["public_id"])
    assert any(event["event_type"] == "import_created" for event in events)


# -- approvals ------------------------------------------------------------------------


def test_request_approval_binds_target_fingerprint(settings: Settings) -> None:
    case = _finalize_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval_service = ExternalDatasetSampleApprovalService(settings)
    approval = approval_service.request_approval(
        sample_import["public_id"],
        {
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 20_000_000,
        },
        admin_id=ADMIN_ID,
    )
    assert approval["status"] == "pending"
    assert approval["target_fingerprint"]
    refreshed = DatasetSampleImportRepository(settings.resolved_database_path).get_sample_import(
        sample_import["public_id"]
    )
    assert refreshed["status"] == "awaiting_approval"


def test_approve_succeeds_when_case_unchanged(settings: Settings) -> None:
    case = _finalize_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval_service = ExternalDatasetSampleApprovalService(settings)
    approval = approval_service.request_approval(
        sample_import["public_id"],
        {
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 20_000_000,
        },
        admin_id=ADMIN_ID,
    )
    approved = approval_service.approve(
        approval["public_id"],
        admin_id=ADMIN_ID,
        approved_record_limit=500,
        approved_byte_limit=20_000_000,
        expires_at="2026-12-31T00:00:00",
    )
    assert approved["status"] == "approved"


def test_approve_raises_when_case_changed_since_request(settings: Settings) -> None:
    case = _finalize_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval_service = ExternalDatasetSampleApprovalService(settings)
    approval = approval_service.request_approval(
        sample_import["public_id"],
        {
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 20_000_000,
        },
        admin_id=ADMIN_ID,
    )

    # Simulate the underlying source changing after approval was requested.
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    verification.update_case_reverification_fields(
        case["public_id"], {"verification_expiry_status": "source_changed"}
    )

    with pytest.raises(DatasetSampleImportError):
        approval_service.approve(
            approval["public_id"],
            admin_id=ADMIN_ID,
            approved_record_limit=500,
            approved_byte_limit=20_000_000,
            expires_at="2026-12-31T00:00:00",
        )


def test_reject_moves_sample_import_to_rejected(settings: Settings) -> None:
    case = _finalize_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval_service = ExternalDatasetSampleApprovalService(settings)
    approval = approval_service.request_approval(
        sample_import["public_id"],
        {
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 20_000_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.reject(approval["public_id"], admin_id=ADMIN_ID, reason="Not needed")
    refreshed = DatasetSampleImportRepository(settings.resolved_database_path).get_sample_import(
        sample_import["public_id"]
    )
    assert refreshed["status"] == "rejected"
