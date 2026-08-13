"""MB-41: API tests for the RAG-build fields of
/admin/mini-brain/external-ai-gateway-dataset-bridge/sessions/{id}/export-to-dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.rag import RagRepository
from backend.models.rag import EmbeddingModelCreate, KnowledgeSpaceCreate
from backend.services.external_ai_provider_client import MockProviderClient
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from backend.services.rag_ingestion_service import RagIngestionService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

BRIDGE = "/api/admin/mini-brain/external-ai-gateway-dataset-bridge"
KNOWN_PHRASE = "KAVERI-MANGO-4471"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _admin_public_id(app: FastAPI, username: str) -> str:
    with database_connection(app.state.settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT public_id FROM admin_accounts WHERE username=?", (username,)
        ).fetchone()
    return row["public_id"]


def _build_accepted_session(settings: Settings, admin_id: str, canned_text: str) -> str:
    gateway = MiniBrainExternalAiGatewayService(
        settings, provider_clients={"mock1": MockProviderClient(provider_key="mock1", canned_text=canned_text)},
    )
    session = gateway.create_session(topic="MB-41 API bridge test", purpose="data_acquisition_assistance", admin_id=admin_id)
    sid = session["public_id"]
    gateway.run_validate_authorization_stage(sid, authorization_note="api rag build test", admin_id=admin_id)
    gateway.run_sanitize_inputs_stage(sid, admin_stated_need="api test need", admin_id=admin_id)
    gateway.run_select_providers_stage(sid, requested_provider_keys=["mock1"], admin_id=admin_id)
    gateway.run_dispatch_requests_stage(sid, admin_id=admin_id)
    gateway.run_collect_responses_stage(sid, admin_id=admin_id)
    gateway.run_normalize_responses_stage(sid, admin_id=admin_id)
    gateway.run_analyze_agreement_stage(sid, admin_id=admin_id)
    gateway.run_build_evidence_stage(sid, admin_id=admin_id)
    gateway.generate_report_stage(sid, admin_id=admin_id)
    session = gateway.admin_review(sid, decision="accept", admin_id=admin_id)
    assert session["status"] == "admin_accepted"
    return sid


async def test_build_rag_index_over_http_creates_real_rag_objects(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    admin_id = await _admin_public_id(api_app, "dataset-admin")

    rag_ingestion = RagIngestionService(RagRepository(api_app.state.settings.resolved_database_path), api_app.state.settings)
    rag_ingestion.create_embedding_model(
        EmbeddingModelCreate(
            name="api-test-embedder", version="1", provider_type="local_custom_embedding",
            dimensions=64, maximum_input_tokens=2048, supported_languages=["en"],
        ),
        admin_id,
    )
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 API space", slug="mb41-api-space"), admin_id)

    canned_text = (
        f"MB-41 API verification document. Test phrase: {KNOWN_PHRASE}. "
        "This content is deliberately long enough to clear the chunk-quality minimum-character threshold."
    )
    session_id = _build_accepted_session(api_app.state.settings, admin_id, canned_text)

    response = await client.post(
        f"{BRIDGE}/sessions/{session_id}/export-to-dataset",
        json={
            "ingest_to_rag": True,
            "rag_knowledge_space_public_id": space["public_id"],
            "build_rag_index": True,
            "retrieval_profile_name": "MB-41 API retrieval profile",
        },
        headers=headers,
    )
    try:
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["source_version_public_ids"]) == 1
        assert len(body["chunk_set_public_ids"]) == 1
        assert len(body["embedding_run_public_ids"]) == 1
        assert len(body["vector_index_public_ids"]) == 1
        assert body["retrieval_profile_public_id"]

        events = _bridge_audit_events(api_app, session_id)
        assert "external_gateway_rag_build_started" in events
        assert "external_gateway_rag_build_completed" in events
        assert "external_gateway_rag_build_failed" not in events
    finally:
        await client.aclose()


def _bridge_audit_events(app: FastAPI, session_public_id: str) -> list[str]:
    with database_connection(app.state.settings.resolved_database_path) as connection:
        rows = connection.execute(
            "SELECT event_type FROM audit_logs WHERE resource_public_id=? AND "
            "resource_type='external_gateway_dataset_bridge' ORDER BY id",
            (session_public_id,),
        ).fetchall()
    return [row["event_type"] for row in rows]


async def test_build_rag_index_without_ingest_to_rag_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    admin_id = await _admin_public_id(api_app, "dataset-admin")
    session_id = _build_accepted_session(api_app.state.settings, admin_id, "some content for this test, long enough.")

    response = await client.post(
        f"{BRIDGE}/sessions/{session_id}/export-to-dataset",
        json={"build_rag_index": True},
        headers=headers,
    )
    try:
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_retrieval_profile_created_via_http_is_not_active(api_app: FastAPI) -> None:
    from backend.services.rag_retrieval_service import RagRetrievalService

    client, headers = await authenticated_client(api_app)
    admin_id = await _admin_public_id(api_app, "dataset-admin")

    settings = api_app.state.settings
    rag_ingestion = RagIngestionService(RagRepository(settings.resolved_database_path), settings)
    rag_ingestion.create_embedding_model(
        EmbeddingModelCreate(
            name="api-test-embedder-2", version="1", provider_type="local_custom_embedding",
            dimensions=64, maximum_input_tokens=2048, supported_languages=["en"],
        ),
        admin_id,
    )
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 API space 2", slug="mb41-api-space-2"), admin_id)
    canned_text = "Enough content for a real chunk to be accepted by the quality thresholds here."
    session_id = _build_accepted_session(settings, admin_id, canned_text)

    response = await client.post(
        f"{BRIDGE}/sessions/{session_id}/export-to-dataset",
        json={
            "ingest_to_rag": True, "rag_knowledge_space_public_id": space["public_id"], "build_rag_index": True,
        },
        headers=headers,
    )
    try:
        assert response.status_code == 200, response.text
        body = response.json()
        rag_retrieval = RagRetrievalService(RagRepository(settings.resolved_database_path), settings)
        profile = rag_retrieval.get_profile(body["retrieval_profile_public_id"])
        assert profile["status"] != "active"
    finally:
        await client.aclose()
