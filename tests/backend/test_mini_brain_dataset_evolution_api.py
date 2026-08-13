"""MB-11: API tests for /admin/mini-brain/dataset-evolution.

Auth/CSRF requirements and route wiring over real HTTP. The full
evolution workflow is already proven at the service layer in
test_mini_brain_dataset_evolution_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

DE = "/api/admin/mini-brain/dataset-evolution"


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


def _seed_dataset_source(app: FastAPI, admin_id: str, count: int = 30) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="API DE Set", language="en", source_type="manual"), admin_id,
    )
    for i in range(count):
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="en",
                instruction=f"Q{i}", output_text=f"Answer {i} in reasonable depth for testing purposes.",
                metadata={},
            ),
            admin_id,
        )
    return source["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{DE}/sessions")).status_code == 401
        assert (await client.get(f"{DE}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_writes_no_training(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{DE}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["training_started"] is False
        assert body["models_deployed"] is False
        assert body["dataset_writes_performed"] is False
        assert body["rag_modified"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{DE}/sessions", json={"dataset_source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="de-seed-admin", display_name="S", password="password12345")
        ).public_id
        source_public_id = _seed_dataset_source(api_app, seed_admin_id)

        response = await client.post(f"{DE}/sessions", json={"dataset_source_public_id": source_public_id}, headers=headers)
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "knowledge_evolution"

        response = await client.post(f"{DE}/sessions/{session_id}/knowledge-evolution", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "dataset_evolution"

        response = await client.post(f"{DE}/sessions/{session_id}/dataset-evolution", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "evolution_simulation"

        response = await client.post(f"{DE}/sessions/{session_id}/simulation", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "recommendation"

        response = await client.post(f"{DE}/sessions/{session_id}/recommendation", headers=headers)
        assert response.status_code == 200, response.text

        response = await client.post(f"{DE}/sessions/{session_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["stage"] == "awaiting_admin_review"
        assert session["evolution_report"]["ready_for_admin_review"] is True

        response = await client.post(
            f"{DE}/sessions/{session_id}/admin-review", json={"decision": "reject"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["status"] == "admin_rejected" and session["stage"] == "closed"

        response = await client.get(f"{DE}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 6

        response = await client.get(f"{DE}/sessions", headers=headers)
        assert response.status_code == 200
        assert any(s["public_id"] == session_id for s in response.json()["items"])
    finally:
        await client.aclose()


async def test_send_to_rag_without_approve_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="de-seed-admin", display_name="S", password="password12345")
        ).public_id
        source_public_id = _seed_dataset_source(api_app, seed_admin_id)

        response = await client.post(f"{DE}/sessions", json={"dataset_source_public_id": source_public_id}, headers=headers)
        session_id = response.json()["public_id"]
        await client.post(f"{DE}/sessions/{session_id}/knowledge-evolution", headers=headers)
        await client.post(f"{DE}/sessions/{session_id}/dataset-evolution", headers=headers)
        await client.post(f"{DE}/sessions/{session_id}/simulation", headers=headers)
        await client.post(f"{DE}/sessions/{session_id}/recommendation", headers=headers)
        await client.post(f"{DE}/sessions/{session_id}/report", headers=headers)

        response = await client.post(
            f"{DE}/sessions/{session_id}/admin-review", json={"decision": "send_to_rag"}, headers=headers,
        )
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()
