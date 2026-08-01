from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.main import create_app
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
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
        database_path=tmp_path / "rag_sandbox_evaluation.db",
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


async def test_run_evaluation_records_unsupported_claim_and_language_and_quality(
    api_app: FastAPI,
) -> None:
    settings = api_app.state.settings
    context = _build_ready_index_and_retrieval_run(settings)

    client, headers = await authenticated_client(api_app)
    try:
        assignment_id = await _build_eligible_rag_assignment(
            client, headers, api_app, slug="sandbox-eval"
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
    evaluations = evaluation_service.run_evaluation(
        context["experiment"]["public_id"], answer_run["public_id"], admin_id=ADMIN_ID
    )
    types_present = {row["evaluation_type"] for row in evaluations}
    assert "unsupported_claim" in types_present
    assert "language_compliance" in types_present
    assert "answer_quality" in types_present
    for row in evaluations:
        assert row["automated"] is True

    sandbox = RagSandboxRepository(settings.resolved_database_path)
    stored = sandbox.list_evaluations(context["experiment"]["public_id"])
    assert len(stored) == len(evaluations)

    events = sandbox.list_events(context["experiment"]["public_id"])
    assert any(event["event_type"] == "evaluation_completed" for event in events)


async def test_run_evaluation_raises_for_answer_run_outside_experiment(
    api_app: FastAPI,
) -> None:
    settings = api_app.state.settings
    context = _build_ready_index_and_retrieval_run(settings)
    evaluation_service = RagSandboxEvaluationService(settings)
    with pytest.raises(ValueError, match="answer run not found"):
        evaluation_service.run_evaluation(
            context["experiment"]["public_id"], "does-not-exist", admin_id=ADMIN_ID
        )
