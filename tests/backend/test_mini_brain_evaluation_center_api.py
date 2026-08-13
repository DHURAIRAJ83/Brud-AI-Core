"""MB-19: API tests for /admin/mini-brain/evaluation-center.

Auth/CSRF requirements and route wiring over real HTTP. The full
12-stage workflow is already proven at the service layer in
test_mini_brain_evaluation_center_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service
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
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

EC = "/api/admin/mini-brain/evaluation-center"
TEXT = "Mountain River Fish Tree scene page one."


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


async def _seed_certified_dataset_and_package(app: FastAPI, admin_id: str) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_pdf_with_image())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    vs = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    vs_id = vs["public_id"]
    vi.run_image_extraction_stage(vs_id, admin_id=admin_id)
    vi.run_image_quality_stage(vs_id, admin_id=admin_id)
    vi.run_vision_understanding_stage(vs_id, admin_id=admin_id)
    vi.run_ocr_cross_validation_stage(vs_id, admin_id=admin_id, dataset_text=TEXT)
    vi.run_caption_stage(vs_id, admin_id=admin_id, admin_caption="A mountain scene.")
    vi.run_bounding_box_stage(vs_id, admin_id=admin_id)
    vi.finish_annotation_stage(vs_id, admin_id=admin_id)
    vi.run_knowledge_graph_stage(vs_id, admin_id=admin_id)
    vi.run_qa_generation_stage(vs_id, admin_id=admin_id)
    vi.run_dataset_draft_stage(vs_id, admin_id=admin_id)
    vi.run_quality_score_stage(vs_id, admin_id=admin_id)
    vi.generate_report_stage(vs_id, admin_id=admin_id)
    vi.admin_review(vs_id, decision="approve", admin_id=admin_id)

    mm = MiniBrainMultimodalDatasetGeneratorService(app.state.settings)
    mds = mm.create_session(document_source_public_id=document["public_id"], vision_session_public_id=vs_id, admin_id=admin_id)
    mds_id = mds["public_id"]
    mm.run_collect_sources_stage(mds_id, admin_id=admin_id)
    mm.run_collect_text_stage(mds_id, admin_id=admin_id)
    mm.run_collect_images_stage(mds_id, admin_id=admin_id)
    mm.run_merge_metadata_stage(mds_id, admin_id=admin_id)
    mm.run_conversation_builder_stage(mds_id, admin_id=admin_id)
    mm.run_instruction_builder_stage(mds_id, admin_id=admin_id)
    mm.run_dataset_draft_stage(mds_id, admin_id=admin_id)
    mm.run_quality_analysis_stage(mds_id, admin_id=admin_id)
    mm.run_duplicate_detection_stage(mds_id, admin_id=admin_id)
    mm.generate_report_stage(mds_id, admin_id=admin_id)
    mm.admin_review(mds_id, decision="approve", admin_id=admin_id)

    tp = MiniBrainTrainingPipelineService(app.state.settings)
    tps = tp.create_session(topic="api test package", admin_id=admin_id)
    tp_id = tps["public_id"]
    tp.run_collect_datasets_stage(tp_id, dataset_session_public_ids=[mds_id], admin_id=admin_id)
    tp.run_collect_rag_memory_stage(tp_id, rag_session_public_ids=[], admin_id=admin_id)
    tp.run_analyze_language_stage(tp_id, admin_id=admin_id)
    tp.run_analyze_vision_stage(tp_id, admin_id=admin_id)
    tp.run_analyze_tokenizer_stage(tp_id, admin_id=admin_id)
    tp.run_plan_splits_stage(tp_id, admin_id=admin_id)
    tp.run_plan_curriculum_stage(tp_id, admin_id=admin_id)
    tp.run_estimate_hardware_stage(tp_id, admin_id=admin_id)
    tp.run_build_package_stage(tp_id, admin_id=admin_id)
    tp.generate_report_stage(tp_id, admin_id=admin_id)
    tp.admin_review(tp_id, decision="approve", admin_id=admin_id)

    return mds_id, tp_id


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{EC}/sessions")).status_code == 401
        assert (await client.get(f"{EC}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_training_no_deployment(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{EC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["training_started"] is False
        assert body["fine_tuning_performed"] is False
        assert body["gguf_export_performed"] is False
        assert body["quantization_performed"] is False
        assert body["runtime_activated"] is False
        assert body["models_deployed"] is False
        assert body["model_inference_performed"] is False
        assert body["automatic_approval"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{EC}/sessions", json={"topic": "hello"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="ec-seed-admin", display_name="S", password="password12345")
        ).public_id
        mds_id, tp_id = await _seed_certified_dataset_and_package(api_app, seed_admin_id)

        response = await client.post(f"{EC}/sessions", json={"topic": "http workflow"}, headers=headers)
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "collect_datasets"

        response = await client.post(
            f"{EC}/sessions/{session_id}/collect-datasets",
            json={"dataset_session_public_ids": [mds_id]}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "collect_rag_sessions"

        response = await client.post(
            f"{EC}/sessions/{session_id}/collect-rag-sessions", json={"rag_session_public_ids": []}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "collect_training_packages"

        response = await client.post(
            f"{EC}/sessions/{session_id}/collect-training-packages",
            json={"training_package_session_public_ids": [tp_id]}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "run_language_benchmarks"

        for path in ("language-benchmarks", "ocr-benchmarks", "grounding-retrieval-benchmarks", "multimodal-benchmarks", "package-benchmarks"):
            response = await client.post(f"{EC}/sessions/{session_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        response = await client.post(f"{EC}/sessions/{session_id}/regression", json={}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "generate_report"

        response = await client.post(f"{EC}/sessions/{session_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["stage"] == "awaiting_admin_review"
        assert session["evaluation_report"]["no_model_inference_performed"] is True

        response = await client.post(
            f"{EC}/sessions/{session_id}/admin-review", json={"decision": "approve"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "closed"

        response = await client.get(f"{EC}/sessions/{session_id}/results", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

        response = await client.get(f"{EC}/sessions/{session_id}/exports", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

        response = await client.get(f"{EC}/memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

        response = await client.get(f"{EC}/sessions/{session_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0
    finally:
        await client.aclose()


async def test_language_benchmarks_before_collect_stage_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{EC}/sessions", json={"topic": "out of order"}, headers=headers)
        session_id = response.json()["public_id"]

        response = await client.post(f"{EC}/sessions/{session_id}/language-benchmarks", headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{EC}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_list_sessions_and_memory_routes(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{EC}/sessions", headers=headers)
        assert response.status_code == 200
        response = await client.get(f"{EC}/memory", headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()
