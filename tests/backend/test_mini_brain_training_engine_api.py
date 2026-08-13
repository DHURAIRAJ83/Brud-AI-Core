"""MB-22: API tests for /admin/mini-brain/training-engine.

Auth/CSRF requirements and route wiring over real HTTP. The full
14-stage workflow is already proven at the service layer in
test_mini_brain_training_engine_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service
calls, and that every route requires admin authentication.
"""

from pathlib import Path

import fitz
import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.models.documents import ProcessRequest
from backend.services.document_service import DocumentService
from backend.services.mini_brain_evaluation_center_service import MiniBrainEvaluationCenterService
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_intelligence_service import MiniBrainVisionIntelligenceService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

TE = "/api/admin/mini-brain/training-engine"
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


def _make_text_only_pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), TEXT)
    value = pdf.tobytes()
    pdf.close()
    return value


async def _seed_approved_package_and_release(app: FastAPI, admin_id: str) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_text_only_pdf())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    vs = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    vs_id = vs["public_id"]

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
    tp_session = tp.create_session(topic="api test package", admin_id=admin_id)
    tp_id = tp_session["public_id"]
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

    ev = MiniBrainEvaluationCenterService(app.state.settings)
    ev_session = ev.create_session(topic="api test evaluation", admin_id=admin_id)
    ev_id = ev_session["public_id"]
    ev.run_collect_datasets_stage(ev_id, dataset_session_public_ids=[mds_id], admin_id=admin_id)
    ev.run_collect_rag_sessions_stage(ev_id, rag_session_public_ids=[], admin_id=admin_id)
    ev.run_collect_training_packages_stage(ev_id, training_package_session_public_ids=[tp_id], admin_id=admin_id)
    ev.run_language_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_ocr_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_grounding_retrieval_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_multimodal_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_package_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_regression_comparison_stage(ev_id, admin_id=admin_id)
    ev.generate_report_stage(ev_id, admin_id=admin_id)
    ev.admin_review(ev_id, decision="approve", admin_id=admin_id)

    rg = MiniBrainReleaseGovernanceService(app.state.settings)
    rg_session = rg.create_session(topic="api test release", admin_id=admin_id)
    rg_id = rg_session["public_id"]
    rg.run_collect_datasets_stage(rg_id, dataset_session_public_ids=[mds_id], admin_id=admin_id)
    rg.run_collect_rag_stage(rg_id, rag_session_public_ids=[], admin_id=admin_id)
    rg.run_collect_training_package_stage(rg_id, training_package_session_public_id=tp_id, admin_id=admin_id)
    rg.run_collect_evaluation_stage(rg_id, evaluation_session_public_id=ev_id, admin_id=admin_id)
    rg.run_safety_gates_stage(rg_id, admin_id=admin_id)
    rg.run_compliance_gates_stage(rg_id, admin_id=admin_id)
    rg.run_benchmark_gates_stage(rg_id, admin_id=admin_id)
    rg.run_build_risk_rollback_stage(rg_id, admin_id=admin_id)
    rg.run_build_release_package_stage(rg_id, admin_id=admin_id)
    rg.generate_report_stage(rg_id, admin_id=admin_id)
    rg.admin_review(rg_id, decision="approve", admin_id=admin_id)

    return tp_id, rg_id


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{TE}/jobs")).status_code == 401
        assert (await client.get(f"{TE}/diagnostics")).status_code == 401
        assert (await client.post(f"{TE}/jobs", json={})).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_deployment_or_auto_start(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{TE}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["model_deployed"] is False
        assert body["model_promoted_to_production"] is False
        assert body["auto_start_after_package_approval"] is False
        assert body["existing_checkpoints_ever_overwritten"] is False
        assert body["requires_fresh_admin_authorization_per_job"] is True
        assert body["real_cpu_training_available"] is False
        assert body["real_gpu_training_available"] is False
        assert body["simulation_mode_available"] is True
    finally:
        await client.aclose()


async def test_create_job_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{TE}/jobs", json={
            "topic": "hello", "training_package_session_public_id": "x",
            "release_governance_session_public_id": "y", "execution_mode": "simulation",
        })
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="te-seed-admin", display_name="S", password="password12345")
        ).public_id
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, seed_admin_id)

        response = await client.post(f"{TE}/jobs", json={
            "topic": "http job", "training_package_session_public_id": tp_id,
            "release_governance_session_public_id": rg_id, "execution_mode": "simulation",
        }, headers=headers)
        assert response.status_code == 200, response.text
        job_id = response.json()["public_id"]
        assert response.json()["stage"] == "validate_release"

        response = await client.post(f"{TE}/jobs/{job_id}/validate-release", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "validate_package"

        response = await client.post(f"{TE}/jobs/{job_id}/validate-package", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "validate_authorization"

        response = await client.post(
            f"{TE}/jobs/{job_id}/authorize", json={"authorization_reason": "http test authorization"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "plan_resources"
        assert response.json()["admin_authorization_token"]

        for path in ("plan-resources", "build-manifest", "reserve-runtime", "start"):
            response = await client.post(f"{TE}/jobs/{job_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        job = response.json()
        assert job["status"] == "running"
        assert job["stage"] == "streaming_metrics"

        response = await client.post(f"{TE}/jobs/{job_id}/metrics", json={"step": 0, "epoch": 0}, headers=headers)
        assert response.status_code == 200, response.text
        response = await client.post(f"{TE}/jobs/{job_id}/metrics", json={"step": 100, "epoch": 0}, headers=headers)
        assert response.status_code == 200, response.text

        response = await client.get(f"{TE}/jobs/{job_id}/metrics", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

        response = await client.post(f"{TE}/jobs/{job_id}/checkpoints", json={"step": 100, "epoch": 0}, headers=headers)
        assert response.status_code == 200, response.text

        response = await client.get(f"{TE}/jobs/{job_id}/checkpoints", headers=headers)
        assert response.status_code == 200
        checkpoints = response.json()["items"]
        assert len(checkpoints) == 1

        response = await client.post(f"{TE}/jobs/{job_id}/checkpoints", json={"step": 100, "epoch": 0}, headers=headers)
        assert response.status_code in (400, 422)

        response = await client.post(f"{TE}/jobs/{job_id}/pause", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        response = await client.post(f"{TE}/jobs/{job_id}/resume", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "running"

        response = await client.post(f"{TE}/jobs/{job_id}/finalize", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"

        response = await client.post(f"{TE}/jobs/{job_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        report = response.json()["final_report"]
        assert report["no_deployment_performed"] is True
        assert report["checkpoint_count"] == 1

        response = await client.post(f"{TE}/jobs/{job_id}/archive", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "archived"

        response = await client.get(f"{TE}/memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

        response = await client.get(f"{TE}/jobs/{job_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

        response = await client.get(f"{TE}/jobs/{job_id}/audit", headers=headers)
        assert response.status_code == 200
        assert response.json()["event_count"] > 0
    finally:
        await client.aclose()


async def test_start_before_authorization_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        seed_admin_id = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
            AdminCreate(username="te-seed-admin2", display_name="S", password="password12345")
        ).public_id
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, seed_admin_id)

        response = await client.post(f"{TE}/jobs", json={
            "topic": "out of order", "training_package_session_public_id": tp_id,
            "release_governance_session_public_id": rg_id, "execution_mode": "simulation",
        }, headers=headers)
        job_id = response.json()["public_id"]

        response = await client.post(f"{TE}/jobs/{job_id}/start", headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_get_unknown_job_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{TE}/jobs/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_list_jobs_and_memory_routes(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{TE}/jobs", headers=headers)
        assert response.status_code == 200
        response = await client.get(f"{TE}/memory", headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()
