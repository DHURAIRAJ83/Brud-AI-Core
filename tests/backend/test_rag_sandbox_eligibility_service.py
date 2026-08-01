import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
    RagSandboxError,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_eligibility.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_finalized_sample_import(
    settings: Settings, *, rag_sandbox_eligible: bool = True, rag_use_status: str = "approved"
) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {
            "canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus",
            "declared_licence": "CC-BY-4.0",
        },
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    verification.assess_permission(
        case["public_id"], "rag_use",
        {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
    )
    verification.review_permission(
        case["public_id"], "rag_use",
        status=rag_use_status, reviewed_by=ADMIN_ID, reason="Licence review",
    )
    verification.lock_case(case["public_id"], {"summary": "finalized for test"})

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1",
            "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"],
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sample_file = samples.add_file(
        sample_import["public_id"],
        {
            "original_filename": "corpus.txt", "safe_filename": "corpus.txt",
            "relative_path": "corpus.txt", "declared_format": "txt",
        },
    )
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text", "language": "tamil",
            "raw_content": "தமிழ் உரை", "normalized_content": "தமிழ் உரை",
            "source_checksum": "chk-source-1", "record_checksum": "chk-record-1",
            "status": "accepted",
        },
    )
    with sqlite3.connect(settings.resolved_database_path) as connection:
        record_id = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record["public_id"],),
        ).fetchone()[0]
    samples.add_review(
        sample_import["public_id"],
        {
            "target_type": "record", "target_id": record_id, "decision": "accept",
            "reason": "clean record", "reviewer_admin_public_id": REVIEWER_ID,
        },
    )
    samples.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": rag_sandbox_eligible,
            "training_assessment_status": "not_assessed",
            "report": {"summary": "ok"}, "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    samples.lock_sample_import(
        sample_import["public_id"], report={"summary": "ok"},
        rag_sandbox_eligible=rag_sandbox_eligible, training_assessment_status="not_assessed",
        status="validated",
    )
    return samples.get_sample_import(sample_import["public_id"])


# -- eligibility --------------------------------------------------------------------


def test_check_eligibility_passes_for_finalized_eligible_import(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    service = RagSandboxEligibilityService(settings)
    result = service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is True
    assert result["blocking_reasons"] == []


def test_check_eligibility_blocks_when_rag_sandbox_eligible_false(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings, rag_sandbox_eligible=False)
    service = RagSandboxEligibilityService(settings)
    result = service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is False
    assert any("rag_sandbox_eligible" in reason for reason in result["blocking_reasons"])


def test_check_eligibility_blocks_when_rag_use_permission_denied(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings, rag_use_status="not_approved")
    service = RagSandboxEligibilityService(settings)
    result = service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is False
    assert any("rag_use" in reason for reason in result["blocking_reasons"])


def test_check_eligibility_does_not_require_training_permission(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    service = RagSandboxEligibilityService(settings)
    result = service.check_eligibility(sample_import["public_id"])
    assert "training_permission" not in result["checks"]
    assert result["eligible"] is True


def test_check_eligibility_blocks_when_not_finalized(settings: Settings) -> None:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "X", "normalized_name": "x"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    service = RagSandboxEligibilityService(settings)
    result = service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is False


# -- experiment creation --------------------------------------------------------------


def test_create_experiment_raises_when_not_eligible(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings, rag_sandbox_eligible=False)
    service = RagSandboxEligibilityService(settings)
    with pytest.raises(RagSandboxError):
        service.create_experiment(
            sample_import["public_id"],
            {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
        )


def test_create_experiment_succeeds_and_records_event(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    service = RagSandboxEligibilityService(settings)
    experiment = service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    assert experiment["status"] == "draft"
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    events = sandbox.list_events(experiment["public_id"])
    assert any(event["event_type"] == "experiment_created" for event in events)


# -- approval -----------------------------------------------------------------------


def test_request_approval_binds_target_fingerprint(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation",
            "maximum_records": 100, "maximum_total_characters": 500_000,
            "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    assert approval["target_fingerprint"]
    assert approval["accepted_record_checksums"] == ["chk-record-1"]

    experiment = RagSandboxRepository(settings.resolved_database_path).get_experiment(
        experiment["public_id"]
    )
    assert experiment["status"] == "awaiting_approval"


def test_approve_succeeds_when_unchanged(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    assert approval_service.is_stale(approval["public_id"]) is False
    approved = approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    assert approved["status"] == "approved"

    experiment = RagSandboxRepository(settings.resolved_database_path).get_experiment(
        experiment["public_id"]
    )
    assert experiment["status"] == "approved"


def test_approve_raises_when_accepted_records_changed_since_request(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    # A new report version changes the sample_report_checksum bound at request time.
    samples.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": True, "training_assessment_status": "not_assessed",
            "report": {"summary": "revised"}, "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    assert approval_service.is_stale(approval["public_id"]) is True
    with pytest.raises(RagSandboxError):
        approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)


def test_reject_moves_experiment_to_rejected(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.reject(approval["public_id"], admin_id=ADMIN_ID, reason="not needed")
    experiment = RagSandboxRepository(settings.resolved_database_path).get_experiment(
        experiment["public_id"]
    )
    assert experiment["status"] == "rejected"
