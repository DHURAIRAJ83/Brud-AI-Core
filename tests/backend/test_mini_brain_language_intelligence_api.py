"""MB-13: API tests for /admin/mini-brain/language-intelligence.

Auth/CSRF requirements and route wiring over real HTTP. The full
language workflow is already proven at the service layer in
test_mini_brain_language_intelligence_service.py -- this file confirms
the routes correctly translate HTTP requests into those same service
calls.
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

LI = "/api/admin/mini-brain/language-intelligence"


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


def _seed_dataset_source(app: FastAPI, admin_id: str) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="API LI Set", language="ta", source_type="manual"), admin_id,
    )
    for i, text in enumerate([
        "தமிழ் மொழி மிகவும் பழமையான மொழிகளில் ஒன்றாகும்.",
        "This is an English sentence for testing purposes only.",
        "epadi irukku nga?",
    ]):
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="ta",
                instruction=f"Q{i}", output_text=text, metadata={},
            ),
            admin_id,
        )
    return source["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{LI}/sessions")).status_code == 401
        assert (await client.get(f"{LI}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_writes_no_training_no_rag(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{LI}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["dataset_writes_performed"] is False
        assert body["training_started"] is False
        assert body["rag_called"] is False
        assert body["automatic_approval"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{LI}/sessions", json={"dataset_source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="li-seed-admin", display_name="S", password="password12345")
        ).public_id
        source_public_id = _seed_dataset_source(api_app, seed_admin_id)

        response = await client.post(f"{LI}/sessions", json={"dataset_source_public_id": source_public_id}, headers=headers)
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "language_scan"

        for path in (
            "language-scan", "unicode-validation", "spell-analysis", "grammar-analysis",
            "ocr-analysis", "tanglish-analysis",
        ):
            response = await client.post(f"{LI}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        response = await client.post(
            f"{LI}/sessions/{session_id}/translation-analysis", json={"pairs": []}, headers=headers,
        )
        assert response.status_code == 200, response.text

        for path in ("dataset-draft", "quality-score", "report"):
            response = await client.post(f"{LI}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        session = response.json()
        assert session["stage"] == "awaiting_admin_review"
        assert session["language_report"]["ready_for_admin_review"] is True

        response = await client.post(
            f"{LI}/sessions/{session_id}/admin-review", json={"decision": "approve"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "certified"

        response = await client.get(f"{LI}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 10

        response = await client.get(f"{LI}/sessions", headers=headers)
        assert response.status_code == 200
        assert any(s["public_id"] == session_id for s in response.json()["items"])
    finally:
        await client.aclose()


async def test_spell_analysis_before_unicode_validation_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="li-seed-admin2", display_name="S", password="password12345")
        ).public_id
        source_public_id = _seed_dataset_source(api_app, seed_admin_id)

        response = await client.post(f"{LI}/sessions", json={"dataset_source_public_id": source_public_id}, headers=headers)
        session_id = response.json()["public_id"]

        response = await client.post(f"{LI}/sessions/{session_id}/spell-analysis", headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()
