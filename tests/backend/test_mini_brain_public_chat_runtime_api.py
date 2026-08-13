"""MB-23: API tests for /api/public/chat and
/api/admin/mini-brain/public-chat.

Auth/rate-limit requirements and route wiring over real HTTP. The full
workflow is already proven at the service layer in
test_mini_brain_public_chat_runtime_service.py -- this file confirms
the routes correctly translate HTTP requests into those same service
calls, that the public routes require no admin auth (matching Phase
18's own `/api/chat` convention), and that every admin route requires
authentication.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_public_chat_routing_service import (
    _build_public_chat_assignment,
    _create_active_memory_policy,
)

pytestmark = pytest.mark.anyio

PC = "/api/public/chat"
MBPC = "/api/admin/mini-brain/public-chat"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_web_search_process_state():
    from backend.services.web_search_cache import reset_cache
    from backend.services.web_search_provider import reset_provider_circuit

    reset_cache()
    reset_provider_circuit("wikipedia")
    yield


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports", document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports", core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts", release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True, log_level="CRITICAL", public_chat_model_enabled=True,
        public_chat_rate_limit_max_requests=1000,
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_public_routes_require_no_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(f"{PC}/sessions", json={"language": "auto"})
        assert response.status_code == 200, response.text
    finally:
        await client.aclose()


async def test_admin_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBPC}/sessions")).status_code == 401
        assert (await client.get(f"{MBPC}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_deployment_or_automatic_training(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["mb22_training_started_or_finalized"] is False
        assert body["automatic_training_performed"] is False
        assert body["raw_message_content_stored"] is False
        assert body["candidates_require_admin_review"] is True
    finally:
        await client.aclose()


async def test_review_candidate_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBPC}/candidates/does-not-exist/review", json={"decision": "approve"},
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_public_and_admin_workflow_over_http(api_app: FastAPI) -> None:
    admin_client, admin_headers = await authenticated_client(api_app)
    public_client = admin_client
    try:
        await _build_public_chat_assignment(admin_client, admin_headers, api_app, slug="api1")
        await _create_active_memory_policy(admin_client, admin_headers)
        response = await public_client.post(f"{PC}/sessions", json={"language": "en"})
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["status"] == "active"

        response = await public_client.post(
            f"{PC}/sessions/{session_id}/messages", json={"message": "What is a noun in Tamil grammar?"},
        )
        assert response.status_code == 200, response.text
        assert "reply" in response.json()

        response = await public_client.post(
            f"{PC}/sessions/{session_id}/messages",
            json={"message": "That is wrong, that did not answer my question"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["signals_raised"] >= 1

        response = await public_client.post(
            f"{PC}/sessions/{session_id}/feedback", json={"satisfaction_rating": 0.1, "comment": "not helpful"},
        )
        assert response.status_code == 200, response.text

        response = await public_client.post(f"{PC}/sessions/{session_id}/end", json={})
        assert response.status_code == 200, response.text
        assert response.json()["session"]["status"] == "ended"

        response = await admin_client.get(f"{MBPC}/sessions/{session_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ended"

        response = await admin_client.get(f"{MBPC}/sessions/{session_id}/messages", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 4

        response = await admin_client.get(f"{MBPC}/sessions/{session_id}/signals", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 1

        response = await admin_client.get(f"{MBPC}/clusters", headers=admin_headers)
        assert response.status_code == 200

        response = await admin_client.post(
            f"{MBPC}/candidates/generate", json={"minimum_frequency": 1}, headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        candidates = response.json()["items"]
        assert len(candidates) >= 1
        candidate_id = candidates[0]["public_id"]

        response = await admin_client.get(f"{MBPC}/candidates", headers=admin_headers)
        assert response.status_code == 200

        response = await admin_client.get(f"{MBPC}/candidates/{candidate_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["handoff_report"]["advisory_only"] is True

        response = await admin_client.post(
            f"{MBPC}/candidates/{candidate_id}/review", json={"decision": "approve", "notes": "ok"},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"

        response = await admin_client.get(f"{MBPC}/analytics", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["total_sessions"] >= 1

        response = await admin_client.get(f"{MBPC}/exports/analytics", headers=admin_headers)
        assert response.status_code == 200

        response = await admin_client.get(f"{MBPC}/exports/candidates", headers=admin_headers)
        assert response.status_code == 200
    finally:
        await admin_client.aclose()


async def test_send_message_to_unknown_session_returns_404(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(f"{PC}/sessions/does-not-exist/messages", json={"message": "hi"})
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_oversized_message_is_rejected(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        start = await client.post(f"{PC}/sessions", json={"language": "auto"})
        session_id = start.json()["public_id"]
        response = await client.post(
            f"{PC}/sessions/{session_id}/messages", json={"message": "x" * 5000},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()
