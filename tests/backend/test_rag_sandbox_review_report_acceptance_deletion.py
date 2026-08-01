from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.main import create_app
from backend.services.rag_sandbox_acceptance_service import RagSandboxAcceptanceService
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_deletion_service import RagSandboxDeletionService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
from backend.services.rag_sandbox_human_review_service import RagSandboxHumanReviewService
from backend.services.rag_sandbox_report_service import RagSandboxReportService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_rag_api import _build_eligible_rag_assignment
from tests.backend.test_rag_sandbox_answer_service import _build_ready_index_and_retrieval_run

pytestmark = pytest.mark.anyio

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_lifecycle.db",
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


async def _build_answered_and_evaluated_experiment(api_app: FastAPI) -> dict:
    settings = api_app.state.settings
    context = _build_ready_index_and_retrieval_run(settings)

    client, headers = await authenticated_client(api_app)
    try:
        assignment_id = await _build_eligible_rag_assignment(
            client, headers, api_app, slug="lifecycle"
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
    answer_run = result["answer_runs"][0]

    evaluation_service = RagSandboxEvaluationService(settings)
    evaluation_service.run_evaluation(
        context["experiment"]["public_id"], answer_run["public_id"], admin_id=ADMIN_ID
    )

    return {**context, "answer_run": answer_run, "settings": settings}


async def test_finalize_report_refuses_without_human_review(api_app: FastAPI) -> None:
    context = await _build_answered_and_evaluated_experiment(api_app)
    report_service = RagSandboxReportService(context["settings"])
    with pytest.raises(RagSandboxError):
        report_service.finalize(context["experiment"]["public_id"], admin_id=ADMIN_ID)


async def test_full_review_report_acceptance_deletion_lifecycle(api_app: FastAPI) -> None:
    context = await _build_answered_and_evaluated_experiment(api_app)
    settings = context["settings"]

    review_service = RagSandboxHumanReviewService(settings)
    review_service.review_query(
        context["experiment"]["public_id"],
        context["answer_run"]["query_public_id"],
        {"answer_run_public_id": context["answer_run"]["public_id"],
         "answer_grounded": True, "decision": "pass", "notes": "looks good"},
        admin_id=ADMIN_ID,
    )

    report_service = RagSandboxReportService(settings)
    report = report_service.finalize(context["experiment"]["public_id"], admin_id=ADMIN_ID)
    assert report["production_rag_readiness"] in (
        "not_assessed", "potentially_ready", "ready_with_conditions", "not_ready", "blocked",
    )
    assert "Production RAG Activated" not in str(report["report"])
    assert "Training Approved" not in str(report["report"])

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    experiment_row = sandbox.get_experiment(context["experiment"]["public_id"])
    assert experiment_row["status"] == "needs_review"

    acceptance_service = RagSandboxAcceptanceService(settings)
    acceptance = acceptance_service.decide(
        context["experiment"]["public_id"],
        decision="accepted_with_conditions",
        reason="metrics acceptable with conditions",
        report_public_id=report["public_id"],
        admin_id=ADMIN_ID,
    )
    assert acceptance["decision"] == "accepted_with_conditions"

    experiment_row = sandbox.get_experiment(context["experiment"]["public_id"])
    assert experiment_row["status"] == "accepted_with_conditions"

    # Stale acceptance: a report_public_id that isn't the latest report is rejected.
    with pytest.raises(RagSandboxError):
        acceptance_service.decide(
            context["experiment"]["public_id"],
            decision="accepted",
            reason="trying with a stale report reference",
            report_public_id="not-the-latest-report",
            admin_id=ADMIN_ID,
        )

    deletion_service = RagSandboxDeletionService(settings)
    request = deletion_service.request_deletion(
        context["experiment"]["public_id"], reason="experiment complete", admin_id=ADMIN_ID
    )
    confirmed = deletion_service.confirm_deletion(
        request["deletion_request_code"], admin_id=ADMIN_ID
    )
    assert confirmed["status"] == "confirmed"
    executed = deletion_service.execute_deletion(
        request["deletion_request_code"], admin_id=ADMIN_ID
    )
    assert executed["status"] == "executed"

    experiment_row = sandbox.get_experiment(context["experiment"]["public_id"])
    assert experiment_row["status"] == "deleted"
    corpus = sandbox.get_corpus_for_experiment(context["experiment"]["public_id"])
    assert corpus["status"] == "deleted"

    # Reports and audit-adjacent events survive deletion.
    reports_after_deletion = sandbox.list_reports(context["experiment"]["public_id"])
    assert len(reports_after_deletion) >= 1
    events_after_deletion = sandbox.list_events(context["experiment"]["public_id"])
    assert any(event["event_type"] == "deletion_executed" for event in events_after_deletion)


async def test_execute_deletion_refuses_without_confirmation(api_app: FastAPI) -> None:
    context = await _build_answered_and_evaluated_experiment(api_app)
    settings = context["settings"]
    deletion_service = RagSandboxDeletionService(settings)
    request = deletion_service.request_deletion(
        context["experiment"]["public_id"], reason="test", admin_id=ADMIN_ID
    )
    with pytest.raises(RagSandboxError):
        deletion_service.execute_deletion(request["deletion_request_code"], admin_id=ADMIN_ID)
