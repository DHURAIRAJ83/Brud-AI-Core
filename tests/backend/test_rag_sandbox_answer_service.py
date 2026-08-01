import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.main import create_app
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
)
from backend.services.rag_sandbox_index_service import RagSandboxIndexService
from backend.services.rag_sandbox_query_set_service import RagSandboxQuerySetService
from backend.services.rag_sandbox_retrieval_service import RagSandboxRetrievalService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_rag_api import _build_eligible_rag_assignment

pytestmark = pytest.mark.anyio

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_answer.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _build_ready_index_and_retrieval_run(settings: Settings) -> dict:
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
            "raw_content": "பொங்கல் என்பது தமிழர்களின் முக்கிய அறுவடைத் திருவிழா ஆகும். "
            "இது தை மாதம் முதல் நாளில் கொண்டாடப்படுகிறது.",
            "normalized_content": "பொங்கல் என்பது தமிழர்களின் முக்கிய அறுவடைத் திருவிழா ஆகும். "
            "இது தை மாதம் முதல் நாளில் கொண்டாடப்படுகிறது.",
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
        {"purpose": "grounded_answer_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "grounded_answer_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)

    corpus_service = RagSandboxCorpusService(settings)
    corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)

    index_service = RagSandboxIndexService(settings)
    index_row = index_service.build_index(
        experiment["public_id"], index_kind="hybrid", admin_id=ADMIN_ID
    )

    query_service = RagSandboxQuerySetService(settings)
    query_set = query_service.create_query_set(
        experiment["public_id"], name="Base set", admin_id=ADMIN_ID
    )
    query_service.add_query(
        query_set["public_id"],
        {
            "query_text": "பொங்கல் எப்போது கொண்டாடப்படுகிறது",
            "language": "tamil", "query_type": "fact_lookup",
            "expected_source_ids": [record["public_id"]],
        },
        created_by=ADMIN_ID,
    )
    query_service.finalize_query_set(query_set["public_id"], admin_id=ADMIN_ID)

    retrieval_service = RagSandboxRetrievalService(settings)
    retrieval_run = retrieval_service.run_retrieval(
        experiment["public_id"],
        index_public_id=index_row["public_id"],
        query_set_public_id=query_set["public_id"],
        admin_id=ADMIN_ID,
    )
    return {"experiment": experiment, "retrieval_run": retrieval_run}


async def test_run_generation_produces_sandbox_labeled_answer(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    context = _build_ready_index_and_retrieval_run(settings)

    client, headers = await authenticated_client(api_app)
    try:
        assignment_id = await _build_eligible_rag_assignment(
            client, headers, api_app, slug="sandbox-answer"
        )
    finally:
        await client.aclose()

    answer_service = RagSandboxAnswerService(settings)
    result = answer_service.run_generation(
        context["experiment"]["public_id"],
        retrieval_run_public_id=context["retrieval_run"]["public_id"],
        generation_assignment_public_id=assignment_id,
        admin_id=ADMIN_ID,
    )
    assert len(result["answer_runs"]) == 1
    answer_run = result["answer_runs"][0]
    assert answer_run["status"] in (
        "grounded_answer", "insufficient_evidence", "generation_failed", "blocked_evidence",
    )
    assert answer_run["answer_text"].startswith("Sandbox evaluation output")

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    events = sandbox.list_events(context["experiment"]["public_id"])
    assert any(event["event_type"] == "answer_run_completed" for event in events)

    if answer_run["citation_count"]:
        citations = sandbox.list_citations(answer_run["public_id"])
        assert citations
        assert all(
            citation["validation_status"]
            in ("valid", "partially_supporting", "invalid", "missing")
            for citation in citations
        )
