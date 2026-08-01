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
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_api.db",
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


def _seed_finalized_sample_import(settings: Settings) -> str:
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
            "raw_content": "தமிழ் உரை", "normalized_content": "தமிழ் உரை",
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
    return sample_import["public_id"]


async def test_experiment_lifecycle_via_http(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    sample_import_public_id = _seed_finalized_sample_import(settings)

    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/rag-sandbox/experiments",
            headers=headers,
            json={
                "sample_import_public_id": sample_import_public_id,
                "purpose": "retrieval_validation",
            },
        )
        assert created.status_code == 200, created.text
        experiment_id = created.json()["public_id"]
        assert created.json()["status"] == "draft"

        eligibility = await client.get(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/eligibility", headers=headers
        )
        assert eligibility.status_code == 200
        assert eligibility.json()["eligible"] is True

        approval_requested = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/request-approval",
            headers=headers,
            json={
                "purpose": "retrieval_validation", "maximum_records": 100,
                "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
            },
        )
        assert approval_requested.status_code == 200, approval_requested.text

        approved = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/approve",
            headers=headers,
            json={},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        corpus = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/prepare-corpus",
            headers=headers,
            json={},
        )
        assert corpus.status_code == 200, corpus.text
        assert corpus.json()["record_count"] == 1
        assert corpus.json()["production_visible"] is False

        index_built = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/build-index",
            headers=headers,
            json={"index_kind": "bm25"},
        )
        assert index_built.status_code == 200, index_built.text
        assert index_built.json()["status"] == "active"

        query_set = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/query-sets",
            headers=headers,
            json={"name": "Base set"},
        )
        assert query_set.status_code == 200
        query_set_id = query_set.json()["public_id"]

        added_query = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/query-sets/"
            f"{query_set_id}/queries",
            headers=headers,
            json={"query_text": "தமிழ் என்றால் என்ன?", "language": "tamil",
                  "query_type": "fact_lookup"},
        )
        assert added_query.status_code == 200, added_query.text

        finalized_query_set = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/query-sets/"
            f"{query_set_id}/finalize",
            headers=headers,
            json={},
        )
        assert finalized_query_set.status_code == 200
        assert finalized_query_set.json()["status"] == "finalized"

        retrieval_run = await client.post(
            f"/api/admin/rag-sandbox/experiments/{experiment_id}/run-retrieval",
            headers=headers,
            json={
                "index_public_id": index_built.json()["public_id"],
                "query_set_public_id": query_set_id,
            },
        )
        assert retrieval_run.status_code == 200, retrieval_run.text
        assert retrieval_run.json()["status"] == "completed"

        overview = await client.get("/api/admin/rag-sandbox/overview", headers=headers)
        assert overview.status_code == 200
        assert "rag_sandbox_experiments_ready_for_testing" in overview.json()
    finally:
        await client.aclose()


async def test_mutations_require_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/rag-sandbox/experiments",
            json={"sample_import_public_id": "x", "purpose": "retrieval_validation"},
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_unauthenticated_requests_are_rejected(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/rag-sandbox/overview")
        assert response.status_code in (401, 403)
        response = await client.get("/api/admin/rag-sandbox/experiments")
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_create_experiment_rejects_ineligible_sample_import(api_app: FastAPI) -> None:
    settings = api_app.state.settings
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
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/rag-sandbox/experiments",
            headers=headers,
            json={
                "sample_import_public_id": sample_import["public_id"],
                "purpose": "retrieval_validation",
            },
        )
        assert response.status_code == 422, response.text
    finally:
        await client.aclose()
