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
from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
    RagSandboxError,
)
from backend.services.rag_sandbox_index_service import RagSandboxIndexService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_index.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_ready_corpus(settings: Settings, *, record_count: int = 2) -> dict:
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
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-1",
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
        status="approved", reviewed_by=ADMIN_ID, reason="Licence review",
    )
    verification.lock_case(case["public_id"], {"summary": "finalized for test"})

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
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
    for index in range(record_count):
        record = samples.add_record(
            sample_import["public_id"],
            {
                "source_file_public_id": sample_file["public_id"],
                "modality": "text", "language": "tamil",
                "raw_content": f"தமிழ் உரை பற்றி ஒரு சிறு பத்தி {index}. மேலும் சில தகவல்கள்.",
                "normalized_content": (
                    f"தமிழ் உரை பற்றி ஒரு சிறு பத்தி {index}. மேலும் சில தகவல்கள்."
                ),
                "source_checksum": f"chk-source-{index}", "record_checksum": f"chk-record-{index}",
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
            "rag_sandbox_eligible": True, "training_assessment_status": "not_assessed",
            "report": {"summary": "ok"}, "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    samples.lock_sample_import(
        sample_import["public_id"], report={"summary": "ok"},
        rag_sandbox_eligible=True, training_assessment_status="not_assessed", status="validated",
    )
    sample_import = samples.get_sample_import(sample_import["public_id"])

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
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)

    corpus_service = RagSandboxCorpusService(settings)
    corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)
    return experiment


def test_build_hybrid_index_activates_vector_and_keyword_indexes(settings: Settings) -> None:
    experiment = _build_ready_corpus(settings)
    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind="hybrid", admin_id=ADMIN_ID
    )
    assert index_row["status"] == "active"
    assert index_row["rag_vector_index_id"] is not None
    assert index_row["rag_keyword_index_id"] is not None
    assert index_row["chunk_count"] >= 2

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    experiment_row = sandbox.get_experiment(experiment["public_id"])
    assert experiment_row["status"] == "ready"

    events = sandbox.list_events(experiment["public_id"])
    assert any(event["event_type"] == "index_build_completed" for event in events)


def test_build_bm25_only_index_has_no_vector_index(settings: Settings) -> None:
    experiment = _build_ready_corpus(settings)
    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind="bm25", admin_id=ADMIN_ID
    )
    assert index_row["rag_keyword_index_id"] is not None
    assert index_row["rag_vector_index_id"] is None


def test_build_vector_only_index_has_no_keyword_index(settings: Settings) -> None:
    experiment = _build_ready_corpus(settings)
    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind="vector", admin_id=ADMIN_ID
    )
    assert index_row["rag_vector_index_id"] is not None
    assert index_row["rag_keyword_index_id"] is None


def test_build_index_refuses_unknown_kind(settings: Settings) -> None:
    experiment = _build_ready_corpus(settings)
    index_service = RagSandboxIndexService(settings)
    with pytest.raises(RagSandboxError):
        index_service.build_index(experiment["public_id"], index_kind="graph", admin_id=ADMIN_ID)


def test_build_index_refuses_without_ready_corpus(settings: Settings) -> None:
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
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    experiment = sandbox.create_experiment(
        {
            "experiment_code": "RSE-x",
            "sample_import_public_id": sample_import["public_id"],
            "sample_report_public_id": None,
            "verification_case_public_id": case["public_id"],
            "purpose": "retrieval_validation",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    index_service = RagSandboxIndexService(settings)
    with pytest.raises(RagSandboxError):
        index_service.build_index(experiment["public_id"], index_kind="bm25", admin_id=ADMIN_ID)


def test_delete_index_marks_deleted_and_logs_event(settings: Settings) -> None:
    experiment = _build_ready_corpus(settings)
    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind="bm25", admin_id=ADMIN_ID
    )
    deleted = index_service.delete_index(index_row["public_id"], admin_id=ADMIN_ID)
    assert deleted["status"] == "deleted"
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    events = sandbox.list_events(experiment["public_id"])
    assert any(event["event_type"] == "index_deleted" for event in events)
