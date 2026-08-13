"""MB-10: API tests for /admin/mini-brain/research-center.

Auth/CSRF requirements and route wiring over real HTTP. The full
research workflow is already proven at the service layer in
test_mini_brain_research_center_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

RC = "/api/admin/mini-brain/research-center"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{RC}/sessions")).status_code == 401
        assert (await client.get(f"{RC}/diagnostics")).status_code == 401
        assert (await client.get(f"{RC}/providers")).status_code == 401
        assert (await client.get(f"{RC}/memory")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_external_provider_calls(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{RC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["external_providers_called"] is False
        assert body["ai_model_used"] is False
        assert "rag_first_policy" in body
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{RC}/sessions", json={"topic": "No CSRF"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_provider_registry_seeded_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{RC}/providers", headers=headers)
        assert response.status_code == 200
        keys = {p["provider_key"] for p in response.json()["items"]}
        assert keys == {"claude", "openai", "gemini", "openrouter", "local_model"}
    finally:
        await client.aclose()


async def test_local_draft_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{RC}/sessions", json={"topic": "Cell Biology"}, headers=headers)
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "research_request"

        response = await client.post(f"{RC}/sessions/{session_id}/research-request", json={}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "mode_selection"

        response = await client.post(
            f"{RC}/sessions/{session_id}/mode", json={"mode": "local_draft"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "local_draft"

        response = await client.post(f"{RC}/sessions/{session_id}/local-draft", json={}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "dataset_draft"

        response = await client.post(f"{RC}/sessions/{session_id}/dataset-draft", json={}, headers=headers)
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["stage"] == "awaiting_draft_review"
        assert session["dataset_draft"]["verified"] is False

        response = await client.get(f"{RC}/sessions/{session_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["ready_for_admin_review"] is True

        response = await client.post(
            f"{RC}/sessions/{session_id}/draft-review", json={"decision": "archive"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["status"] == "admin_archived" and session["stage"] == "closed"

        response = await client.post(
            f"{RC}/sessions/{session_id}/memory", json={"notes": "http snapshot"}, headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.get(f"{RC}/memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

        response = await client.get(f"{RC}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 5
    finally:
        await client.aclose()


async def test_send_to_rag_without_accept_returns_422_from_service_validation_error(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{RC}/sessions", json={"topic": "Guard"}, headers=headers)
        session_id = response.json()["public_id"]
        await client.post(f"{RC}/sessions/{session_id}/research-request", json={}, headers=headers)
        await client.post(f"{RC}/sessions/{session_id}/mode", json={"mode": "local_draft"}, headers=headers)
        await client.post(f"{RC}/sessions/{session_id}/local-draft", json={}, headers=headers)
        await client.post(f"{RC}/sessions/{session_id}/dataset-draft", json={}, headers=headers)

        response = await client.post(
            f"{RC}/sessions/{session_id}/draft-review", json={"decision": "send_to_rag"}, headers=headers,
        )
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()
