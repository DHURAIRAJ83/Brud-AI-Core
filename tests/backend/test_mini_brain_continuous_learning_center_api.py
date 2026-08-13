"""MB-09: API tests for /admin/mini-brain/continuous-learning-center.

Auth/CSRF requirements and route wiring over real HTTP. The full
planning workflow is already proven at the service layer in
test_mini_brain_continuous_learning_center_service.py -- this file
confirms the routes correctly translate HTTP requests into those same
service calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBCLC = "/api/admin/mini-brain/continuous-learning-center"


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
        assert (await client.get(f"{MBCLC}/sessions")).status_code == 401
        assert (await client.get(f"{MBCLC}/diagnostics")).status_code == 401
        assert (await client.get(f"{MBCLC}/memory")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_external_provider_calls(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBCLC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["external_providers_called"] is False
        assert body["ai_model_used"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBCLC}/sessions", json={})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_create_and_fetch_session_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        create_response = await client.post(f"{MBCLC}/sessions", headers=headers)
        assert create_response.status_code == 200, create_response.text
        session = create_response.json()
        assert session["stage"] == "knowledge_gap_evolution"
        session_id = session["public_id"]

        get_response = await client.get(f"{MBCLC}/sessions/{session_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["public_id"] == session_id

        list_response = await client.get(f"{MBCLC}/sessions", headers=headers)
        assert any(s["public_id"] == session_id for s in list_response.json()["items"])

        evolve_response = await client.post(
            f"{MBCLC}/sessions/{session_id}/knowledge-gap-evolution", headers=headers
        )
        assert evolve_response.status_code == 200, evolve_response.text
        assert evolve_response.json()["stage"] == "learning_queue"

        events_response = await client.get(f"{MBCLC}/sessions/{session_id}/events", headers=headers)
        event_types = [e["event_type"] for e in events_response.json()["items"]]
        assert "knowledge_gaps_evolved" in event_types

        # wrong-stage guard surfaces as 422 at the HTTP layer too
        wrong_stage = await client.post(
            f"{MBCLC}/sessions/{session_id}/knowledge-gap-evolution", headers=headers
        )
        assert wrong_stage.status_code == 422
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBCLC}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_list_memory_starts_empty(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBCLC}/memory", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []
    finally:
        await client.aclose()
