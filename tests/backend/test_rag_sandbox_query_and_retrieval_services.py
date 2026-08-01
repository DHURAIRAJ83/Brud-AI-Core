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
from backend.services.rag_sandbox_query_set_service import RagSandboxQuerySetService
from backend.services.rag_sandbox_retrieval_service import RagSandboxRetrievalService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_retrieval.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_ready_index(settings: Settings, *, index_kind: str = "hybrid") -> dict:
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
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text", "language": "tamil",
            "raw_content": "தமிழ் நாட்டின் தலைநகரம் சென்னை ஆகும். இது ஒரு பெரிய நகரம்.",
            "normalized_content": "தமிழ் நாட்டின் தலைநகரம் சென்னை ஆகும். இது ஒரு பெரிய நகரம்.",
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

    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind=index_kind, admin_id=ADMIN_ID
    )
    return {
        "experiment": experiment, "index": index_row,
        "sample_record_public_id": record["public_id"],
    }


# -- query set ------------------------------------------------------------------


def test_add_query_rejects_unknown_type(settings: Settings) -> None:
    context = _build_ready_index(settings)
    service = RagSandboxQuerySetService(settings)
    query_set = service.create_query_set(
        context["experiment"]["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    with pytest.raises(RagSandboxError):
        service.add_query(
            query_set["public_id"],
            {"query_text": "q", "query_type": "not_a_real_type"},
            created_by=ADMIN_ID,
        )


def test_finalize_requires_assistant_query_review(settings: Settings) -> None:
    context = _build_ready_index(settings)
    service = RagSandboxQuerySetService(settings)
    query_set = service.create_query_set(
        context["experiment"]["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    query = service.add_query(
        query_set["public_id"],
        {"query_text": "தமிழ் நாட்டின் தலைநகரம் எது?", "language": "tamil",
         "query_type": "fact_lookup", "human_authored": False},
        created_by="assistant",
    )
    with pytest.raises(RagSandboxError):
        service.finalize_query_set(query_set["public_id"], admin_id=ADMIN_ID)
    service.review_query(query["public_id"], admin_id=ADMIN_ID)
    finalized = service.finalize_query_set(query_set["public_id"], admin_id=ADMIN_ID)
    assert finalized["status"] == "finalized"


# -- retrieval --------------------------------------------------------------------


def test_run_retrieval_computes_metrics_for_expected_source(settings: Settings) -> None:
    context = _build_ready_index(settings)
    query_service = RagSandboxQuerySetService(settings)
    query_set = query_service.create_query_set(
        context["experiment"]["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    query_service.add_query(
        query_set["public_id"],
        {
            "query_text": "தமிழ் நாட்டின் தலைநகரம் எது?", "language": "tamil",
            "query_type": "fact_lookup",
            "expected_source_ids": [context["sample_record_public_id"]],
        },
        created_by=ADMIN_ID,
    )
    query_service.finalize_query_set(query_set["public_id"], admin_id=ADMIN_ID)

    retrieval_service = RagSandboxRetrievalService(settings)
    run = retrieval_service.run_retrieval(
        context["experiment"]["public_id"],
        index_public_id=context["index"]["public_id"],
        query_set_public_id=query_set["public_id"],
        admin_id=ADMIN_ID,
    )
    assert run["status"] == "completed"

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    results = sandbox.list_retrieval_results(run["public_id"])
    assert len(results) == 1
    assert results[0]["metric_availability"] == "full"
    assert results[0]["expected_source_hit"] is True
    assert results[0]["recall_at_k"] == 1.0

    experiment_row = sandbox.get_experiment(context["experiment"]["public_id"])
    assert experiment_row["status"] == "running_retrieval"


def test_run_retrieval_marks_metric_not_available_without_expected_sources(
    settings: Settings,
) -> None:
    context = _build_ready_index(settings, index_kind="bm25")
    query_service = RagSandboxQuerySetService(settings)
    query_set = query_service.create_query_set(
        context["experiment"]["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    query_service.add_query(
        query_set["public_id"],
        {"query_text": "சென்னை பற்றி சொல்லுங்கள்", "language": "tamil",
         "query_type": "fact_lookup"},
        created_by=ADMIN_ID,
    )
    query_service.finalize_query_set(query_set["public_id"], admin_id=ADMIN_ID)

    retrieval_service = RagSandboxRetrievalService(settings)
    run = retrieval_service.run_retrieval(
        context["experiment"]["public_id"],
        index_public_id=context["index"]["public_id"],
        query_set_public_id=query_set["public_id"],
        admin_id=ADMIN_ID,
    )
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    results = sandbox.list_retrieval_results(run["public_id"])
    assert results[0]["metric_availability"] == "not_available"
    assert results[0]["expected_source_hit"] is None


def test_run_retrieval_refuses_unfinalized_query_set(settings: Settings) -> None:
    context = _build_ready_index(settings)
    query_service = RagSandboxQuerySetService(settings)
    query_set = query_service.create_query_set(
        context["experiment"]["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    retrieval_service = RagSandboxRetrievalService(settings)
    with pytest.raises(RagSandboxError):
        retrieval_service.run_retrieval(
            context["experiment"]["public_id"],
            index_public_id=context["index"]["public_id"],
            query_set_public_id=query_set["public_id"],
            admin_id=ADMIN_ID,
        )
