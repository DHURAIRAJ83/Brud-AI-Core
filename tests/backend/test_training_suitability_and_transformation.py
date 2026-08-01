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
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
)
from backend.services.training_example_transformation_service import (
    TrainingExampleTransformationService,
)
from backend.services.training_suitability_service import (
    TrainingSuitabilityAssessmentService,
    TrainingSuitabilityError,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "training_suitability.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_accepted_experiment(
    settings: Settings, *, training_permission_status: str = "approved",
    record_text: str | None = None, code_suffix: str = "1",
) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {
            "session_code": f"session-{code_suffix}",
            "requested_by_admin_public_id": ADMIN_ID,
        }
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
            "verification_code": f"VC-{code_suffix}",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    for permission_type, status in (
        ("rag_use", "approved"), ("training_use", training_permission_status),
        ("commercial_use", "approved"),
    ):
        verification.assess_permission(
            case["public_id"], permission_type,
            {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
        )
        verification.review_permission(
            case["public_id"], permission_type,
            status=status, reviewed_by=ADMIN_ID, reason="Licence review",
        )
    verification.lock_case(case["public_id"], {"summary": "finalized for test"})

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": f"SI-{code_suffix}",
            "verification_case_public_id": case["public_id"],
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
    content = record_text or "தமிழ் என்றால் என்ன? தமிழ் ஒரு திராவிட மொழி."
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text", "language": "tamil",
            "raw_content": content, "normalized_content": content,
            "source_checksum": "chk-source-0", "record_checksum": "chk-record-0",
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
        {"purpose": "training_data_suitability_research", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "training_data_suitability_research", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)

    corpus_service = RagSandboxCorpusService(settings)
    corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)

    # Fabricate a finalized report + acceptance directly -- Phase 13's own
    # retrieval/generation/evaluation pipeline is exhaustively tested in
    # its own test suite; this test only needs an *accepted* Phase 13
    # report to exist, not to re-derive one end to end.
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    report = sandbox.add_report(
        experiment["public_id"],
        {
            "report": {"summary": "fabricated for phase 14 test"},
            "report_checksum_sha256": "chk-report-1",
            "production_rag_readiness": "potentially_ready",
            "training_data_observation": "potentially_useful",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    sandbox.add_acceptance(
        experiment["public_id"],
        {
            "report_public_id": report["public_id"], "decision": "accepted",
            "reason": "good enough for phase 14 test", "reviewer_admin_public_id": ADMIN_ID,
            "report_checksum_sha256": report["report_checksum_sha256"],
            "target_fingerprint": "fp-1",
        },
    )
    records = sandbox.list_records(experiment["public_id"])
    return {"experiment": experiment, "records": records, "sample_import": sample_import}


# -- suitability assessment ----------------------------------------------------------------


def test_create_assessment_requires_accepted_rag_sandbox_report(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    assert assessment["status"] == "not_assessed"
    assert assessment["rag_sandbox_experiment_public_id"] == built["experiment"]["public_id"]


def test_create_assessment_rejects_when_no_acceptance_exists(settings: Settings) -> None:
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
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    experiment = sandbox.create_experiment(
        {
            "experiment_code": "RSE-x", "sample_import_public_id": sample_import["public_id"],
            "sample_report_public_id": None, "verification_case_public_id": case["public_id"],
            "purpose": "training_data_suitability_research",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    service = TrainingSuitabilityAssessmentService(settings)
    with pytest.raises(TrainingSuitabilityError):
        service.create_assessment(experiment["public_id"], admin_id=ADMIN_ID)


def test_run_assessment_classifies_instruction_response_as_suitable_for_sft(
    settings: Settings,
) -> None:
    built = _build_accepted_experiment(settings)
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    result = service.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)
    assert result["status"] == "assessed"

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    items = training.list_items(assessment["public_id"])
    assert len(items) == 1
    assert items[0]["suitability_status"] == "suitable_for_sft"
    assert items[0]["record_category"] == "instruction_response"
    assert items[0]["reason"]


def test_run_assessment_blocks_when_training_permission_denied(settings: Settings) -> None:
    built = _build_accepted_experiment(settings, training_permission_status="not_approved")
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    service.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    items = training.list_items(assessment["public_id"])
    assert items[0]["suitability_status"] == "blocked"
    assert "licence_training_permission" in items[0]["reason"]


def test_run_assessment_routes_volatile_content_to_rag_only(settings: Settings) -> None:
    built = _build_accepted_experiment(
        settings, record_text="இன்று சென்னையில் விலை அதிகரித்துள்ளது."
    )
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    service.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    items = training.list_items(assessment["public_id"])
    assert items[0]["suitability_status"] == "rag_only"
    assert items[0]["record_category"] == "volatile_knowledge"


# -- transformation --------------------------------------------------------------------------


def _assess_and_get_item(settings: Settings) -> dict:
    built = _build_accepted_experiment(settings)
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    service.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    return training.list_items(assessment["public_id"])[0]


def test_transform_creates_candidate_for_suitable_item(settings: Settings) -> None:
    item = _assess_and_get_item(settings)
    service = TrainingExampleTransformationService(settings)
    candidate = service.transform(
        item["public_id"],
        {
            "transformation_type": "instruction_response_pair",
            "prompt_text": "தமிழ் என்றால் என்ன?",
            "assistant_text": "தமிழ் ஒரு திராவிட மொழி.",
            "language": "tamil",
            "source_checksum": "chk-record-0",
        },
        admin_id=ADMIN_ID,
    )
    assert candidate["review_status"] == "pending_review"
    assert candidate["candidate_checksum"]


def test_transform_rejects_evaluation_only_item(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    service = TrainingSuitabilityAssessmentService(settings)
    assessment = service.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    item = training.add_item(
        assessment["public_id"],
        {"record_category": "evaluation_example", "suitability_status": "evaluation_only",
         "reason": "linked to a Phase 13 query set"},
    )
    transformation_service = TrainingExampleTransformationService(settings)
    with pytest.raises(TrainingSuitabilityError):
        transformation_service.transform(
            item["public_id"],
            {
                "transformation_type": "instruction_response_pair", "source_checksum": "x",
            },
            admin_id=ADMIN_ID,
        )


def test_review_candidate_approve(settings: Settings) -> None:
    item = _assess_and_get_item(settings)
    service = TrainingExampleTransformationService(settings)
    candidate = service.transform(
        item["public_id"],
        {
            "transformation_type": "instruction_response_pair",
            "prompt_text": "q", "assistant_text": "a", "source_checksum": "s",
        },
        admin_id=ADMIN_ID,
    )
    reviewed = service.review_candidate(
        candidate["public_id"],
        {"decision": "approved", "reason": "looks correct"},
        admin_id=ADMIN_ID,
    )
    assert reviewed["review_status"] == "approved"
    assert reviewed["reviewed_by"] == ADMIN_ID


def test_review_candidate_with_revision_updates_text_and_checksum(settings: Settings) -> None:
    item = _assess_and_get_item(settings)
    service = TrainingExampleTransformationService(settings)
    candidate = service.transform(
        item["public_id"],
        {
            "transformation_type": "correction_pair",
            "prompt_text": "தமிழ் தவறு", "assistant_text": "பிழையான பதில்", "source_checksum": "s",
        },
        admin_id=ADMIN_ID,
    )
    original_checksum = candidate["candidate_checksum"]
    reviewed = service.review_candidate(
        candidate["public_id"],
        {
            "decision": "needs_revision", "reason": "ambiguous Tamil correction, needs rework",
            "revised_assistant_text": "திருத்தப்பட்ட பதில்",
        },
        admin_id=ADMIN_ID,
    )
    assert reviewed["review_status"] == "needs_revision"
    assert reviewed["assistant_text"] == "திருத்தப்பட்ட பதில்"
    assert reviewed["candidate_checksum"] != original_checksum

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    revisions = training.list_revisions(candidate["public_id"])
    assert len(revisions) == 1
    assert revisions[0]["decision"] == "needs_revision"


def test_review_candidate_requires_a_reason(settings: Settings) -> None:
    item = _assess_and_get_item(settings)
    service = TrainingExampleTransformationService(settings)
    candidate = service.transform(
        item["public_id"],
        {"transformation_type": "instruction_response_pair", "source_checksum": "s"},
        admin_id=ADMIN_ID,
    )
    with pytest.raises(TrainingSuitabilityError):
        service.review_candidate(
            candidate["public_id"], {"decision": "approved", "reason": ""}, admin_id=ADMIN_ID
        )
