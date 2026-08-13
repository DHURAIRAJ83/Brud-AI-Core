"""MB-12: API tests for /admin/mini-brain/pipeline-coordinator.

Auth/CSRF requirements and route wiring over real HTTP. The full
linking workflow is already proven at the service layer in
test_mini_brain_pipeline_coordinator_service.py -- this file confirms
the routes correctly translate HTTP requests into those same service
calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

PC = "/api/admin/mini-brain/pipeline-coordinator"


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
        assert (await client.get(f"{PC}/sessions")).status_code == 401
        assert (await client.get(f"{PC}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_training_no_rag_calls(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{PC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["training_started"] is False
        assert body["models_deployed"] is False
        assert body["rag_sandbox_called_directly"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{PC}/sessions", json={"topic": "No CSRF"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_link_research_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="pc-seed-admin", display_name="S", password="password12345")
        ).public_id
        mb09_session = MiniBrainContinuousLearningCenterService(api_app.state.settings).create_session(admin_id=seed_admin_id)

        response = await client.post(f"{PC}/sessions", json={"topic": "HTTP Topic"}, headers=headers)
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "new"

        response = await client.post(
            f"{PC}/sessions/{session_id}/link-research",
            json={"mb09_session_public_id": mb09_session["public_id"]}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "under_research"

        response = await client.get(f"{PC}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 2

        response = await client.get(f"{PC}/sessions", headers=headers)
        assert response.status_code == 200
        assert any(s["public_id"] == session_id for s in response.json()["items"])

        response = await client.post(
            f"{PC}/sessions/{session_id}/admin-decision", json={"decision": "archive"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "archived"
    finally:
        await client.aclose()


async def test_link_research_center_before_research_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{PC}/sessions", json={"topic": "Skip"}, headers=headers)
        session_id = response.json()["public_id"]

        response = await client.post(
            f"{PC}/sessions/{session_id}/link-research-center",
            json={"mb10_session_public_id": "does-not-exist"}, headers=headers,
        )
        assert response.status_code in (400, 404, 422)
    finally:
        await client.aclose()
