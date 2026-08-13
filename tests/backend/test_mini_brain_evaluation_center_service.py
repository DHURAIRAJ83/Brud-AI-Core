"""MB-19: service-level tests for MiniBrainEvaluationCenterService
against a real, seeded temp database -- no mocks. A real certified
MB-16 multimodal dataset (built from a real certified MB-14 vision
session), a real approved MB-17 grounded RAG session, and a real
approved MB-18 training package are built first, then MB-19's full
12-stage workflow is driven end to end over them: real benchmark
metrics are computed, real export files are written and checksummed,
a real evaluation & release readiness report is generated, and a real
permanent memory record is created on approval.
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
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.models.auth import AdminCreate
from backend.models.documents import ProcessRequest
from backend.services.document_service import DocumentService
from backend.services.mini_brain_evaluation_center_service import MiniBrainEvaluationCenterService
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService

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


def _create_admin(app: FastAPI, username: str = "ec-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainEvaluationCenterService:
    return MiniBrainEvaluationCenterService(app.state.settings)


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


def _make_text_only_pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), TEXT)
    value = pdf.tobytes()
    pdf.close()
    return value


async def _seed_certified_multimodal_dataset(app: FastAPI, admin_id: str, *, with_image: bool = True) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    content = _make_pdf_with_image() if with_image else _make_text_only_pdf()
    upload_file = _FakeUploadFile("scene.pdf", content)
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    vs = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    vs_id = vs["public_id"]
    vi.run_image_extraction_stage(vs_id, admin_id=admin_id)
    vi.run_image_quality_stage(vs_id, admin_id=admin_id)
    vi.run_vision_understanding_stage(vs_id, admin_id=admin_id)
    vi.run_ocr_cross_validation_stage(vs_id, admin_id=admin_id, dataset_text=TEXT)
    vi.run_caption_stage(vs_id, admin_id=admin_id, admin_caption="A mountain scene with a river.")
    vi.run_bounding_box_stage(vs_id, admin_id=admin_id)
    if with_image:
        objects = vi.list_objects(vs_id, status="active")["items"]
        if objects:
            vi.annotate(vs_id, action="rename", object_public_id=objects[0]["public_id"], payload={"label": "Mountain"}, admin_id=admin_id)
            vi.annotate(vs_id, action="redraw_box", object_public_id=objects[0]["public_id"], payload={"bounding_box": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}}, admin_id=admin_id)
        image_public_id = vi.list_images(vs_id)["items"][0]["public_id"]
        vi.annotate(vs_id, action="add", object_public_id=None, payload={"image_public_id": image_public_id, "label": "River", "confidence": 1.0, "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}, admin_id=admin_id)
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
    session = mm.admin_review(mds_id, decision="approve", admin_id=admin_id)
    assert session["status"] == "admin_approved"
    return mds_id, vs_id


async def _seed_approved_rag_session(app: FastAPI, mds_id: str, admin_id: str, query: str = "Where is the river located?") -> str:
    vr = MiniBrainVisionRagService(app.state.settings)
    session = vr.create_session(multimodal_dataset_session_public_id=mds_id, query=query, admin_id=admin_id)
    vr_id = session["public_id"]
    vr.run_text_retrieval_stage(vr_id, admin_id=admin_id)
    vr.run_ocr_retrieval_stage(vr_id, admin_id=admin_id)
    vr.run_image_retrieval_stage(vr_id, admin_id=admin_id)
    vr.run_object_retrieval_stage(vr_id, admin_id=admin_id)
    vr.run_knowledge_graph_retrieval_stage(vr_id, admin_id=admin_id)
    vr.run_evidence_fusion_stage(vr_id, admin_id=admin_id)
    vr.run_grounded_answer_stage(vr_id, admin_id=admin_id)
    vr.run_quality_evaluation_stage(vr_id, admin_id=admin_id)
    vr.run_hallucination_check_stage(vr_id, admin_id=admin_id)
    vr.generate_report_stage(vr_id, admin_id=admin_id)
    vr.admin_review(vr_id, decision="approve", admin_id=admin_id)
    return vr_id


async def _seed_approved_training_package(app: FastAPI, mds_id: str, rag_ids: list[str], admin_id: str, topic: str = "pkg") -> str:
    tp = MiniBrainTrainingPipelineService(app.state.settings)
    session = tp.create_session(topic=topic, admin_id=admin_id)
    tp_id = session["public_id"]
    tp.run_collect_datasets_stage(tp_id, dataset_session_public_ids=[mds_id], admin_id=admin_id)
    tp.run_collect_rag_memory_stage(tp_id, rag_session_public_ids=rag_ids, admin_id=admin_id)
    tp.run_analyze_language_stage(tp_id, admin_id=admin_id)
    tp.run_analyze_vision_stage(tp_id, admin_id=admin_id)
    tp.run_analyze_tokenizer_stage(tp_id, admin_id=admin_id)
    tp.run_plan_splits_stage(tp_id, admin_id=admin_id)
    tp.run_plan_curriculum_stage(tp_id, admin_id=admin_id)
    tp.run_estimate_hardware_stage(tp_id, admin_id=admin_id)
    tp.run_build_package_stage(tp_id, admin_id=admin_id)
    tp.generate_report_stage(tp_id, admin_id=admin_id)
    session = tp.admin_review(tp_id, decision="approve", admin_id=admin_id)
    assert session["status"] == "admin_approved"
    return tp_id


async def _run_to_report(
    svc: MiniBrainEvaluationCenterService, session_public_id: str, admin_id: str, *,
    dataset_ids: list[str], rag_ids: list[str], package_ids: list[str],
) -> dict:
    session = svc.run_collect_datasets_stage(session_public_id, dataset_session_public_ids=dataset_ids, admin_id=admin_id)
    session = svc.run_collect_rag_sessions_stage(session["public_id"], rag_session_public_ids=rag_ids, admin_id=admin_id)
    session = svc.run_collect_training_packages_stage(session["public_id"], training_package_session_public_ids=package_ids, admin_id=admin_id)
    session = svc.run_language_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_grounding_retrieval_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_multimodal_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_package_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_regression_comparison_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle: dataset + RAG session + training package ------------------------------------


async def test_full_cycle_with_real_certified_sources(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="full cycle evaluation", admin_id=admin_id)
    assert session["stage"] == "collect_datasets"

    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_ids=[tp_id])
    assert session["stage"] == "awaiting_admin_review"
    assert session["evaluation_report"]["no_model_inference_performed"] is True
    assert session["package_benchmark_report"]["missing_file_count"] == 0

    export_dir = Path(session["export_directory"])
    for name in ("benchmark_summary.json", "benchmark_details.json", "regression_report.json", "release_readiness.json", "export_manifest.json"):
        assert (export_dir / name).exists()

    exports = svc.session(session["public_id"])["export_manifest"]["artifacts"]
    assert len(exports) == 4  # export_manifest.json itself is never self-listed

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_approved"

    memory = svc.list_memory()["items"]
    assert len(memory) == 1
    assert memory[0]["source_dataset_count"] == 1

    results = svc.list_results(session["public_id"])["items"]
    assert len(results) > 0
    assert {"language", "ocr", "grounding", "retrieval", "multimodal", "package"} & {r["category"] for r in results}


async def test_text_only_dataset_has_zero_image_coverage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="text-only pkg")

    svc = _svc(api_app)
    session = svc.create_session(topic="text-only evaluation", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_ids=[tp_id])
    assert session["multimodal_benchmark_report"]["image_coverage"] == 0.0
    assert session["grounding_benchmark_report"]["session_count"] == 0


async def test_multimodal_dataset_has_nonzero_image_coverage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=True)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="multimodal pkg")

    svc = _svc(api_app)
    session = svc.create_session(topic="multimodal evaluation", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_ids=[tp_id])
    assert session["multimodal_benchmark_report"]["image_coverage"] > 0.0


async def test_low_grounding_quality_dataset_blocks_release(api_app: FastAPI) -> None:
    """A query far outside the document's own content produces low
    grounding/retrieval signal -- release readiness must honestly
    reflect that, never claim Ready regardless of input quality."""
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id, query="zzz qqq xxx yyy unrelated nonsense")
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="low grounding pkg")

    svc = _svc(api_app)
    session = svc.create_session(topic="low grounding evaluation", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_ids=[tp_id])
    assert session["release_readiness"]["status"] in {"Blocked", "Needs Review"}


# -- certified-source enforcement ------------------------------------------------------------


async def test_collect_datasets_rejects_uncertified_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    documents = DocumentService(api_app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_text_only_pdf())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    uncertified = mm.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[uncertified["public_id"]], admin_id=admin_id)


async def test_collect_rag_sessions_rejects_unapproved_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    unapproved = vr.create_session(multimodal_dataset_session_public_id=mds_id, query="anything", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    report = svc.run_collect_rag_sessions_stage(
        session["public_id"], rag_session_public_ids=[unapproved["public_id"]], admin_id=admin_id,
    )
    assert report["rag_collection_report"]["accepted_count"] == 0
    assert report["rag_collection_report"]["rejected_count"] == 1


async def test_collect_training_packages_rejects_session_without_built_package(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    unbuilt = tp.create_session(topic="unbuilt", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_sessions_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    report = svc.run_collect_training_packages_stage(
        session["public_id"], training_package_session_public_ids=[unbuilt["public_id"]], admin_id=admin_id,
    )
    assert report["package_collection_report"]["accepted_count"] == 0
    assert report["package_collection_report"]["rejected_count"] == 1


# -- package integrity failure -----------------------------------------------------------------


async def test_package_integrity_benchmark_detects_a_corrupted_artifact(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="corrupt me")

    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    tp_session = tp.session(tp_id)
    package_dir = Path(tp_session["package_directory"])
    first_artifact = tp.list_packages(tp_id)["items"][0]
    (package_dir / first_artifact["relative_path"]).write_text("corrupted content", encoding="utf-8")

    svc = _svc(api_app)
    session = svc.create_session(topic="corruption check", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_sessions_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session = svc.run_collect_training_packages_stage(session["public_id"], training_package_session_public_ids=[tp_id], admin_id=admin_id)
    session = svc.run_language_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_grounding_retrieval_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_multimodal_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_package_benchmarks_stage(session["public_id"], admin_id=admin_id)
    assert session["package_benchmark_report"]["missing_file_count"] == 1

    session = svc.run_regression_comparison_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    assert session["release_readiness"]["status"] == "Blocked"
    assert any("package integrity" in issue for issue in session["release_readiness"]["blocking_issues"])


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_language_benchmarks_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_package_benchmarks_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- regression-worse-than-baseline ----------------------------------------------------------


async def test_regression_worse_than_baseline_reports_high_risk(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="baseline pkg")

    svc = _svc(api_app)
    baseline_session = svc.create_session(topic="baseline", admin_id=admin_id)
    baseline_session = await _run_to_report(
        svc, baseline_session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_ids=[tp_id],
    )
    svc.admin_review(baseline_session["public_id"], decision="approve", admin_id=admin_id)

    mds2_id, _vs2_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp2_id = await _seed_approved_training_package(api_app, mds2_id, [], admin_id, topic="worse pkg")

    current_session = svc.create_session(topic="worse than baseline", admin_id=admin_id)
    current_session = svc.run_collect_datasets_stage(current_session["public_id"], dataset_session_public_ids=[mds2_id], admin_id=admin_id)
    current_session = svc.run_collect_rag_sessions_stage(current_session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    current_session = svc.run_collect_training_packages_stage(current_session["public_id"], training_package_session_public_ids=[tp2_id], admin_id=admin_id)
    current_session = svc.run_language_benchmarks_stage(current_session["public_id"], admin_id=admin_id)
    current_session = svc.run_ocr_benchmarks_stage(current_session["public_id"], admin_id=admin_id)
    current_session = svc.run_grounding_retrieval_benchmarks_stage(current_session["public_id"], admin_id=admin_id)
    current_session = svc.run_multimodal_benchmarks_stage(current_session["public_id"], admin_id=admin_id)
    current_session = svc.run_package_benchmarks_stage(current_session["public_id"], admin_id=admin_id)
    current_session = svc.run_regression_comparison_stage(
        current_session["public_id"], admin_id=admin_id, baseline_session_public_id=baseline_session["public_id"],
    )
    assert current_session["regression_report"]["has_baseline"] is True
    assert len(current_session["regression_report"]["regressed_metrics"]) > 0
    assert current_session["regression_report"]["release_risk_level"] in {"medium", "high"}


async def test_regression_comparison_rejects_non_approved_baseline(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="p")

    svc = _svc(api_app)
    not_approved = svc.create_session(topic="not approved baseline", admin_id=admin_id)

    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_sessions_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session = svc.run_collect_training_packages_stage(session["public_id"], training_package_session_public_ids=[tp_id], admin_id=admin_id)
    session = svc.run_language_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_grounding_retrieval_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_multimodal_benchmarks_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_package_benchmarks_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_regression_comparison_stage(
            session["public_id"], admin_id=admin_id, baseline_session_public_id=not_approved["public_id"],
        )


# -- export generation --------------------------------------------------------------------------


async def test_export_manifest_checksums_match_real_files(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="export check")

    svc = _svc(api_app)
    session = svc.create_session(topic="export check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_ids=[tp_id])

    export_dir = Path(session["export_directory"])
    from core_model.release.artifact_inventory import file_checksum

    for artifact in session["export_manifest"]["artifacts"]:
        path = export_dir / artifact["relative_path"]
        assert file_checksum(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["file_size_bytes"]


# -- no-upstream-modification proofs -------------------------------------------------------------


async def test_upstream_sources_never_modified(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="unmodified check")

    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    mds_before = mm.session(mds_id)
    vr_before = vr.session(vr_id)
    tp_before = tp.session(tp_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="unmodified check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_ids=[tp_id])
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    assert mm.session(mds_id) == mds_before
    assert vr.session(vr_id) == vr_before
    assert tp.session(tp_id) == tp_before


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="p")
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_ids=[tp_id])
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)
