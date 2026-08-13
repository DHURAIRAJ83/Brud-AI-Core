"""MB-20: service-level tests for MiniBrainReleaseGovernanceService
against a real, seeded temp database -- no mocks. Real certified MB-16
datasets, real approved MB-17 grounded RAG sessions, real approved
MB-18 training packages, and real approved MB-19 evaluations are built
first, then MB-20's full 12-stage workflow is driven end to end over
them: real safety/compliance/benchmark gates run against real
upstream signals, real artifact files are written and checksummed, a
real release readiness report is generated, and a real permanent
memory record is created on approval.
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
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
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


def _create_admin(app: FastAPI, username: str = "rg-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainReleaseGovernanceService:
    return MiniBrainReleaseGovernanceService(app.state.settings)


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


async def _seed_approved_evaluation(app: FastAPI, mds_id: str, rag_ids: list[str], tp_id: str, admin_id: str, topic: str = "eval") -> str:
    ev = MiniBrainEvaluationCenterService(app.state.settings)
    session = ev.create_session(topic=topic, admin_id=admin_id)
    ev_id = session["public_id"]
    ev.run_collect_datasets_stage(ev_id, dataset_session_public_ids=[mds_id], admin_id=admin_id)
    ev.run_collect_rag_sessions_stage(ev_id, rag_session_public_ids=rag_ids, admin_id=admin_id)
    ev.run_collect_training_packages_stage(ev_id, training_package_session_public_ids=[tp_id], admin_id=admin_id)
    ev.run_language_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_ocr_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_grounding_retrieval_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_multimodal_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_package_benchmarks_stage(ev_id, admin_id=admin_id)
    ev.run_regression_comparison_stage(ev_id, admin_id=admin_id)
    ev.generate_report_stage(ev_id, admin_id=admin_id)
    session = ev.admin_review(ev_id, decision="approve", admin_id=admin_id)
    assert session["status"] == "admin_approved"
    return ev_id


async def _run_to_report(svc: MiniBrainReleaseGovernanceService, session_public_id: str, admin_id: str, *, dataset_ids, rag_ids, package_id, evaluation_id) -> dict:
    session = svc.run_collect_datasets_stage(session_public_id, dataset_session_public_ids=dataset_ids, admin_id=admin_id)
    session = svc.run_collect_rag_stage(session["public_id"], rag_session_public_ids=rag_ids, admin_id=admin_id)
    session = svc.run_collect_training_package_stage(session["public_id"], training_package_session_public_id=package_id, admin_id=admin_id)
    session = svc.run_collect_evaluation_stage(session["public_id"], evaluation_session_public_id=evaluation_id, admin_id=admin_id)
    session = svc.run_safety_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_compliance_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_benchmark_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_build_risk_rollback_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_build_release_package_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle: multimodal + RAG (triggers real OCR conflict -> safety fail / release blocked) ------


async def test_full_cycle_safety_fail_and_release_blocked(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=True)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id)
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [vr_id], tp_id, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="blocked release", admin_id=admin_id)
    assert session["stage"] == "collect_datasets"

    session = await _run_to_report(
        svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_id=tp_id, evaluation_id=ev_id,
    )
    assert session["stage"] == "awaiting_admin_review"
    assert session["safety_gate_report"]["overall_status"] == "fail"
    assert session["readiness_report"]["final_recommendation"] == "not_approved"
    assert session["readiness_report"]["no_deployment_performed"] is True

    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


# -- text-only, no-RAG scenario: safety pass / release approved-or-conditional ----------------------


async def test_text_only_no_rag_safety_pass_path(api_app: FastAPI) -> None:
    """Without any RAG evidence, the grounding/OCR/retrieval safety
    gates have no signal to evaluate and honestly pass via their own
    None-is-not-a-failure rule -- Unicode/Tamil/package/duplicate gates
    still run against real, clean synthetic text and must pass."""
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="text only pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [], tp_id, admin_id, topic="text only eval")

    svc = _svc(api_app)
    session = svc.create_session(topic="approved release", admin_id=admin_id)
    session = await _run_to_report(
        svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_id=tp_id, evaluation_id=ev_id,
    )
    assert session["safety_gate_report"]["overall_status"] == "pass"
    assert session["readiness_report"]["final_recommendation"] in ("approved_for_release", "conditionally_approved")

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["status"] == "admin_approved"


# -- benchmark fail path -------------------------------------------------------------------------


async def test_benchmark_gate_fails_on_high_ocr_conflict(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=True)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="bench fail pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [vr_id], tp_id, admin_id, topic="bench fail eval")

    svc = _svc(api_app)
    session = svc.create_session(topic="benchmark fail", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_stage(session["public_id"], rag_session_public_ids=[vr_id], admin_id=admin_id)
    session = svc.run_collect_training_package_stage(session["public_id"], training_package_session_public_id=tp_id, admin_id=admin_id)
    session = svc.run_collect_evaluation_stage(session["public_id"], evaluation_session_public_id=ev_id, admin_id=admin_id)
    session = svc.run_safety_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_compliance_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_benchmark_gates_stage(session["public_id"], admin_id=admin_id)
    assert session["benchmark_gate_report"]["overall_benchmark_status"] == "fail"
    assert any(m["metric_name"] == "ocr_conflict_ratio" for m in session["benchmark_gate_report"]["failed_metrics"])


# -- compliance gate structurally cannot hard-fail once collection has succeeded ---------------------


async def test_compliance_gates_never_hard_fail_after_valid_collection(api_app: FastAPI) -> None:
    """By the time run_compliance_gates_stage is reachable, stage-order
    guards already guarantee dataset_approval_present and
    audit_trail_present are both true -- so the service-level gate
    call can never hard-fail; the compliance_evaluator module's own
    fail path is proven directly in test_mini_brain_release_governance_core.py."""
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="compliance pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [], tp_id, admin_id, topic="compliance eval")

    svc = _svc(api_app)
    session = svc.create_session(topic="compliance check", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session = svc.run_collect_training_package_stage(session["public_id"], training_package_session_public_id=tp_id, admin_id=admin_id)
    session = svc.run_collect_evaluation_stage(session["public_id"], evaluation_session_public_id=ev_id, admin_id=admin_id)
    session = svc.run_safety_gates_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_compliance_gates_stage(session["public_id"], admin_id=admin_id)
    assert session["compliance_gate_report"]["overall_status"] != "fail"
    assert session["compliance_gate_report"]["blocking_reasons"] == []


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


async def test_collect_training_package_rejects_unapproved_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    unbuilt = tp.create_session(topic="unbuilt", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_collect_training_package_stage(session["public_id"], training_package_session_public_id=unbuilt["public_id"], admin_id=admin_id)


async def test_collect_evaluation_rejects_unapproved_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="eval reject pkg")
    ev = MiniBrainEvaluationCenterService(api_app.state.settings)
    unapproved = ev.create_session(topic="unapproved eval", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session = svc.run_collect_rag_stage(session["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session = svc.run_collect_training_package_stage(session["public_id"], training_package_session_public_id=tp_id, admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_collect_evaluation_stage(session["public_id"], evaluation_session_public_id=unapproved["public_id"], admin_id=admin_id)


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_safety_gates_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_build_release_package_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- deterministic package hash / artifact integrity / rollback plan generation -----------------------


async def test_reproducibility_input_checksum_identical_across_two_sessions_over_same_sources(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="repro pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [], tp_id, admin_id, topic="repro eval")

    svc = _svc(api_app)
    session_a = svc.create_session(topic="repro a", admin_id=admin_id)
    session_a = await _run_to_report(svc, session_a["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_id=tp_id, evaluation_id=ev_id)
    session_b = svc.create_session(topic="repro b", admin_id=admin_id)
    session_b = await _run_to_report(svc, session_b["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_id=tp_id, evaluation_id=ev_id)

    checksum_a = session_a["release_manifest"]["reproducibility"]["input_set_checksum_sha256"]
    checksum_b = session_b["release_manifest"]["reproducibility"]["input_set_checksum_sha256"]
    assert checksum_a == checksum_b


async def test_artifact_files_match_recorded_checksums_and_rollback_plan_present(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="integrity pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [], tp_id, admin_id, topic="integrity eval")

    svc = _svc(api_app)
    session = svc.create_session(topic="integrity check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_id=tp_id, evaluation_id=ev_id)

    from core_model.release.artifact_inventory import file_checksum

    artifacts = svc.list_artifacts(session["public_id"])["items"]
    assert len(artifacts) == session["release_manifest"]["artifact_count"] + 2
    release_dir = Path(session["release_directory"])
    for artifact in artifacts:
        path = release_dir / artifact["relative_path"]
        assert file_checksum(path) == artifact["sha256"]

    rollback_plan = session["risk_rollback_report"]["rollback_plan"]
    assert len(rollback_plan["rollback_steps"]) > 0
    assert (release_dir / "rollback_plan.json").exists()


# -- byte-level proofs upstream sessions never modified ------------------------------------------


async def test_all_four_upstream_phases_byte_identical_before_and_after(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=True)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [vr_id], admin_id, topic="unmodified pkg")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [vr_id], tp_id, admin_id, topic="unmodified eval")

    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    tp = MiniBrainTrainingPipelineService(api_app.state.settings)
    ev = MiniBrainEvaluationCenterService(api_app.state.settings)
    mds_before = mm.session(mds_id)
    vr_before = vr.session(vr_id)
    tp_before = tp.session(tp_id)
    ev_before = ev.session(ev_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="unmodified check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id], package_id=tp_id, evaluation_id=ev_id)
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    assert mm.session(mds_id) == mds_before
    assert vr.session(vr_id) == vr_before
    assert tp.session(tp_id) == tp_before
    assert ev.session(ev_id) == ev_before


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)
    tp_id = await _seed_approved_training_package(api_app, mds_id, [], admin_id, topic="p")
    ev_id = await _seed_approved_evaluation(api_app, mds_id, [], tp_id, admin_id, topic="e")
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[], package_id=tp_id, evaluation_id=ev_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)
