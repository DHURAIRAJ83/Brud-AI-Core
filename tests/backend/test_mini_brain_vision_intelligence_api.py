"""MB-14: API tests for /admin/mini-brain/vision-intelligence.

Auth/CSRF requirements and route wiring over real HTTP. The full
vision workflow is already proven at the service layer in
test_mini_brain_vision_intelligence_service.py -- this file confirms
the routes correctly translate HTTP requests into those same service
calls.
"""

from io import BytesIO
from pathlib import Path

import fitz
import pytest
from fastapi import FastAPI
from PIL import Image

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.models.documents import ProcessRequest
from backend.services.document_service import DocumentService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

VI = "/api/admin/mini-brain/vision-intelligence"


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


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._content[self._offset : self._offset + size]
        self._offset += size
        return chunk


def _make_pdf_with_image() -> bytes:
    png_image = Image.new("RGB", (200, 150), color=(120, 130, 140))
    buffer = BytesIO()
    png_image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Mountain River Fish Tree scene page one.")
    page.insert_image(fitz.Rect(72, 200, 272, 350), stream=png_bytes)
    value = pdf.tobytes()
    pdf.close()
    return value


async def _seed_document_with_image(app: FastAPI, admin_id: str) -> str:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_pdf_with_image())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)
    return document["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{VI}/sessions")).status_code == 401
        assert (await client.get(f"{VI}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_vision_model_no_writes_no_training(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{VI}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["vision_model_available"] is False
        assert body["object_detection_model_available"] is False
        assert body["captioning_model_available"] is False
        assert body["dataset_writes_performed"] is False
        assert body["training_started"] is False
        assert body["runtime_activated"] is False
        assert body["gguf_exported"] is False
        assert body["rag_modified"] is False
        assert body["automatic_approval"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{VI}/sessions", json={"document_source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="vi-seed-admin", display_name="S", password="password12345")
        ).public_id
        document_public_id = await _seed_document_with_image(api_app, seed_admin_id)

        response = await client.post(
            f"{VI}/sessions", json={"document_source_public_id": document_public_id}, headers=headers,
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "image_extraction"

        for path in ("image-extraction", "image-quality", "vision-understanding"):
            response = await client.post(f"{VI}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        response = await client.post(
            f"{VI}/sessions/{session_id}/ocr-cross-validation",
            json={"dataset_text": "Mountain River Fish Tree scene page one."}, headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.post(
            f"{VI}/sessions/{session_id}/caption", json={"admin_caption": "A mountain scene."}, headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.post(f"{VI}/sessions/{session_id}/bounding-box-plan", headers=headers)
        assert response.status_code == 200, response.text

        response = await client.get(f"{VI}/sessions/{session_id}/objects?status=active", headers=headers)
        assert response.status_code == 200
        unknown_object = response.json()["items"][0]

        response = await client.post(
            f"{VI}/sessions/{session_id}/annotate",
            json={"action": "rename", "object_public_id": unknown_object["public_id"], "payload": {"label": "Mountain"}},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.post(f"{VI}/sessions/{session_id}/annotation/finish", headers=headers)
        assert response.status_code == 200, response.text

        for path in ("knowledge-graph", "qa-generation", "dataset-draft", "quality-score", "report"):
            response = await client.post(f"{VI}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        session = response.json()
        assert session["stage"] == "awaiting_admin_review"
        assert session["vision_report"]["ready_for_admin_review"] is True

        response = await client.post(
            f"{VI}/sessions/{session_id}/admin-review", json={"decision": "approve"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "certified"

        response = await client.get(f"{VI}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 8

        response = await client.get(f"{VI}/sessions/{session_id}/images", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

        response = await client.get(f"{VI}/sessions", headers=headers)
        assert response.status_code == 200
        assert any(s["public_id"] == session_id for s in response.json()["items"])
    finally:
        await client.aclose()


async def test_image_quality_before_extraction_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="vi-seed-admin2", display_name="S", password="password12345")
        ).public_id
        document_public_id = await _seed_document_with_image(api_app, seed_admin_id)

        response = await client.post(
            f"{VI}/sessions", json={"document_source_public_id": document_public_id}, headers=headers,
        )
        session_id = response.json()["public_id"]

        response = await client.post(f"{VI}/sessions/{session_id}/image-quality", headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()
