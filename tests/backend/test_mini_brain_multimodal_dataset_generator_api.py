"""MB-16: API tests for /admin/mini-brain/multimodal-dataset-generator.

Auth/CSRF requirements and route wiring over real HTTP. The full
generation workflow is already proven at the service layer in
test_mini_brain_multimodal_dataset_generator_service.py -- this file
confirms the routes correctly translate HTTP requests into those same
service calls.
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
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MD = "/api/admin/mini-brain/multimodal-dataset-generator"
TEXT = "Mountain River Fish Tree scene page one."


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
    page.insert_text((72, 72), TEXT)
    page.insert_image(fitz.Rect(72, 200, 272, 350), stream=png_bytes)
    value = pdf.tobytes()
    pdf.close()
    return value


async def _seed_certified_mb14_session(app: FastAPI, admin_id: str) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_pdf_with_image())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    session = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    session = vi.run_image_extraction_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_image_quality_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_vision_understanding_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_ocr_cross_validation_stage(session["public_id"], admin_id=admin_id, dataset_text=TEXT)
    session = vi.run_caption_stage(session["public_id"], admin_id=admin_id, admin_caption="A mountain scene.")
    session = vi.run_bounding_box_stage(session["public_id"], admin_id=admin_id)
    session = vi.finish_annotation_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_knowledge_graph_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_qa_generation_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_quality_score_stage(session["public_id"], admin_id=admin_id)
    session = vi.generate_report_stage(session["public_id"], admin_id=admin_id)
    session = vi.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    return document["public_id"], session["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MD}/sessions")).status_code == 401
        assert (await client.get(f"{MD}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_writes_no_training(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MD}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["dataset_studio_writes_performed"] is False
        assert body["document_workspace_writes_performed"] is False
        assert body["training_started"] is False
        assert body["automatic_export"] is False
        assert body["automatic_approval"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MD}/sessions", json={"document_source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="md-seed-admin", display_name="S", password="password12345")
        ).public_id
        document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, seed_admin_id)

        response = await client.post(
            f"{MD}/sessions",
            json={"document_source_public_id": document_public_id, "vision_session_public_id": vision_session_public_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "collect_sources"

        for path in (
            "collect-sources", "collect-text", "collect-images", "merge-metadata", "conversation-builder",
            "instruction-builder", "dataset-draft", "quality-analysis", "duplicate-detection", "report",
        ):
            response = await client.post(f"{MD}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        session = response.json()
        assert session["stage"] == "awaiting_admin_review"
        assert session["dataset_report"]["ready_for_admin_review"] is True

        response = await client.post(
            f"{MD}/sessions/{session_id}/admin-review", json={"decision": "approve"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "certified"

        response = await client.get(f"{MD}/sessions/{session_id}/records", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

        response = await client.post(
            f"{MD}/sessions/{session_id}/export-draft", json={"export_format": "json"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["record_count"] > 0

        response = await client.get(f"{MD}/dataset-memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_collect_images_before_collect_text_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="md-seed-admin2", display_name="S", password="password12345")
        ).public_id
        document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, seed_admin_id)

        response = await client.post(
            f"{MD}/sessions",
            json={"document_source_public_id": document_public_id, "vision_session_public_id": vision_session_public_id},
            headers=headers,
        )
        session_id = response.json()["public_id"]

        response = await client.post(f"{MD}/sessions/{session_id}/collect-images", headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()
