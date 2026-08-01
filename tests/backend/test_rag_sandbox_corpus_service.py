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

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_corpus.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_finalized_sample_import(
    settings: Settings, *, record_count: int = 1, decision: str = "accept"
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
    records = []
    for index in range(record_count):
        record = samples.add_record(
            sample_import["public_id"],
            {
                "source_file_public_id": sample_file["public_id"],
                "modality": "text", "language": "tamil",
                "raw_content": f"தமிழ் உரை {index}", "normalized_content": f"தமிழ் உரை {index}",
                "source_checksum": f"chk-source-{index}", "record_checksum": f"chk-record-{index}",
                "status": "accepted",
            },
        )
        with sqlite3.connect(settings.resolved_database_path) as connection:
            record_id = connection.execute(
                "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
                (record["public_id"],),
            ).fetchone()[0]
        review_values = {
            "target_type": "record", "target_id": record_id, "decision": decision,
            "reason": "clean record", "reviewer_admin_public_id": REVIEWER_ID,
        }
        if decision in ("edit_derived_copy", "redact_derived_copy"):
            review_values["derived_content_text"] = f"edited தமிழ் {index}"
            review_values["derived_content_checksum"] = f"chk-derived-{index}"
        samples.add_review(sample_import["public_id"], review_values)
        records.append(record)

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
    return {
        "sample_import": samples.get_sample_import(sample_import["public_id"]),
        "records": records,
    }


def _create_approved_experiment(settings: Settings, sample_import: dict) -> dict:
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
    return experiment


def test_prepare_corpus_promotes_accepted_record(settings: Settings) -> None:
    built = _build_finalized_sample_import(settings)
    experiment = _create_approved_experiment(settings, built["sample_import"])

    corpus_service = RagSandboxCorpusService(settings)
    corpus = corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)
    assert corpus["status"] == "ready"
    assert corpus["record_count"] == 1
    assert corpus["production_visible"] is False

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    records = sandbox.list_records(experiment["public_id"])
    assert len(records) == 1
    assert records[0]["content"] == "தமிழ் உரை 0"
    assert records[0]["rag_source_id"] is not None
    assert records[0]["rag_source_version_id"] is not None

    experiment_row = sandbox.get_experiment(experiment["public_id"])
    assert experiment_row["current_stage"] == "index_build"

    events = sandbox.list_events(experiment["public_id"])
    assert any(event["event_type"] == "record_promoted" for event in events)
    assert any(event["event_type"] == "corpus_prepared" for event in events)


def test_prepare_corpus_uses_derived_content_for_redacted_review(settings: Settings) -> None:
    built = _build_finalized_sample_import(settings, decision="redact_derived_copy")
    experiment = _create_approved_experiment(settings, built["sample_import"])

    corpus_service = RagSandboxCorpusService(settings)
    corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    records = sandbox.list_records(experiment["public_id"])
    assert records[0]["content"] == "edited தமிழ் 0"
    assert records[0]["content_checksum"] == "chk-derived-0"


def test_prepare_corpus_blocks_record_without_promotion_eligible_decision(
    settings: Settings,
) -> None:
    built = _build_finalized_sample_import(settings, decision="needs_more_evidence")
    experiment = _create_approved_experiment(settings, built["sample_import"])

    corpus_service = RagSandboxCorpusService(settings)
    with pytest.raises(RagSandboxError):
        corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)


def test_prepare_corpus_refuses_without_approved_approval(settings: Settings) -> None:
    built = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        built["sample_import"]["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    corpus_service = RagSandboxCorpusService(settings)
    with pytest.raises(RagSandboxError):
        corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)


def test_prepare_corpus_refuses_a_second_time(settings: Settings) -> None:
    built = _build_finalized_sample_import(settings)
    experiment = _create_approved_experiment(settings, built["sample_import"])
    corpus_service = RagSandboxCorpusService(settings)
    corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)
    with pytest.raises(RagSandboxError):
        corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)
