"""MB-22: service-level tests for MiniBrainTrainingEngineService
against a real, seeded temp database -- no mocks. A real, admin-
approved MB-18 training package and a real, admin-approved MB-20
release-governance session are built first (text-only, no-RAG safety-
pass path, mirroring MB-20's own test suite), then MB-22's full
14-stage workflow is driven end to end over them using the real
`SimulationTrainingAdapter`: authorization guards, stage-order guards,
metric streaming, checkpoint no-overwrite, pause/resume, cancel,
finalize, report generation, and archive are all exercised against a
real database and real filesystem artifacts.
"""

from io import BytesIO
from pathlib import Path

import fitz
import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.models.auth import AdminCreate
from backend.models.documents import ProcessRequest
from backend.services.document_service import DocumentService
from backend.services.mini_brain_evaluation_center_service import MiniBrainEvaluationCenterService
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_intelligence_service import MiniBrainVisionIntelligenceService

pytestmark = pytest.mark.anyio

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


def _create_admin(app: FastAPI, username: str = "te-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainTrainingEngineService:
    return MiniBrainTrainingEngineService(app.state.settings)


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


async def _seed_approved_package_and_release(app: FastAPI, admin_id: str, topic: str = "te pkg") -> tuple[str, str]:
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
    tp_session = tp.create_session(topic=topic, admin_id=admin_id)
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
    ev_session = ev.create_session(topic=f"{topic} eval", admin_id=admin_id)
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
    rg_session = rg.create_session(topic=f"{topic} release", admin_id=admin_id)
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


async def _drive_job_to_streaming(svc: MiniBrainTrainingEngineService, tp_id: str, rg_id: str, admin_id: str, *, topic: str = "job") -> str:
    job = svc.create_job(
        topic=topic, training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="simulation", admin_id=admin_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="test authorization", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id)
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    return job_id


# -- full end-to-end workflow ------------------------------------------------------------------


async def test_full_workflow_create_to_archive(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id)
    svc = _svc(api_app)
    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    rg = MiniBrainReleaseGovernanceService(api_app.state.settings)
    tp_before = tp.session(tp_id)
    rg_before = rg.session(rg_id)

    job_id = await _drive_job_to_streaming(svc, tp_id, rg_id, admin_id)
    job = svc.job(job_id)
    assert job["status"] == "running"
    assert job["stage"] == "streaming_metrics"
    assert job["admin_authorization_token"]

    for step in (0, 100, 200):
        job = svc.run_stream_metric_stage(job_id, step=step, epoch=0, admin_id=admin_id)
    metrics = svc.list_metrics(job_id)["items"]
    assert len(metrics) == 3
    assert metrics[0]["loss"] > metrics[-1]["loss"]

    svc.run_save_checkpoint_stage(job_id, step=200, epoch=0, admin_id=admin_id)
    checkpoints = svc.list_checkpoints(job_id)["items"]
    assert len(checkpoints) == 1
    assert checkpoints[0]["checkpoint_name"] == "checkpoint-epoch000-step00000200"
    assert checkpoints[0]["is_metadata_only"] is True
    assert len(checkpoints[0]["sha256"]) == 64

    job = svc.pause(job_id, admin_id=admin_id)
    assert job["status"] == "paused"
    job = svc.resume(job_id, admin_id=admin_id)
    assert job["status"] == "running"

    job = svc.finalize(job_id, admin_id=admin_id)
    assert job["status"] == "completed"
    assert job["stage"] == "generate_report"

    job = svc.generate_report_stage(job_id, admin_id=admin_id)
    report = job["final_report"]
    assert report["checkpoint_count"] == 1
    assert report["no_deployment_performed"] is True

    job = svc.archive(job_id, admin_id=admin_id)
    assert job["status"] == "archived"

    memory = svc.list_memory()["items"]
    assert any(m["final_status"] == "completed" for m in memory)

    tp_after = tp.session(tp_id)
    rg_after = rg.session(rg_id)
    assert tp_after == tp_before, "MB-18 session was mutated by MB-22"
    assert rg_after == rg_before, "MB-20 session was mutated by MB-22"


# -- stage-order guard tests -------------------------------------------------------------------


async def test_cannot_authorize_before_validation_stages(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="order pkg")
    svc = _svc(api_app)
    job = svc.create_job(
        topic="order job", training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="simulation", admin_id=admin_id,
    )
    with pytest.raises(ValidationError):
        svc.run_validate_authorization_stage(job["public_id"], authorization_reason="skip ahead", admin_id=admin_id)


async def test_cannot_start_training_before_reserving_runtime(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="order2 pkg")
    svc = _svc(api_app)
    job = svc.create_job(
        topic="order2 job", training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="simulation", admin_id=admin_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="test", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_start_training_stage(job_id, admin_id=admin_id)


async def test_validate_authorization_rejects_empty_reason(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="empty reason pkg")
    svc = _svc(api_app)
    job = svc.create_job(
        topic="empty reason job", training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="simulation", admin_id=admin_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_validate_authorization_stage(job_id, authorization_reason="   ", admin_id=admin_id)


# -- checkpoint no-overwrite ------------------------------------------------------------------


async def test_checkpoint_overwrite_is_rejected(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="ckpt pkg")
    svc = _svc(api_app)
    job_id = await _drive_job_to_streaming(svc, tp_id, rg_id, admin_id, topic="ckpt job")
    svc.run_stream_metric_stage(job_id, step=100, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=100, epoch=0, admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_save_checkpoint_stage(job_id, step=100, epoch=0, admin_id=admin_id)


# -- cancel flow ------------------------------------------------------------------------------


async def test_cancel_flow(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="cancel pkg")
    svc = _svc(api_app)
    job_id = await _drive_job_to_streaming(svc, tp_id, rg_id, admin_id, topic="cancel job")
    job = svc.cancel(job_id, admin_id=admin_id)
    assert job["status"] == "cancelled"
    assert job["stage"] == "cancelled"
    job = svc.archive(job_id, admin_id=admin_id)
    assert job["status"] == "archived"


async def test_archive_rejected_before_completion(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="early archive pkg")
    svc = _svc(api_app)
    job_id = await _drive_job_to_streaming(svc, tp_id, rg_id, admin_id, topic="early archive job")
    with pytest.raises(ValidationError):
        svc.archive(job_id, admin_id=admin_id)


# -- authorization/validation failure paths ----------------------------------------------------


async def test_validate_release_rejects_unapproved_release_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="unapproved pkg")
    rg = MiniBrainReleaseGovernanceService(api_app.state.settings)
    other_session = rg.create_session(topic="not approved release", admin_id=admin_id)
    svc = _svc(api_app)
    job = svc.create_job(
        topic="unapproved job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=other_session["public_id"], execution_mode="simulation", admin_id=admin_id,
    )
    with pytest.raises(ValidationError):
        svc.run_validate_release_stage(job["public_id"], admin_id=admin_id)
