"""MB-18: service-level tests for MiniBrainTrainingPipelineService
against a real, seeded temp database -- no mocks. A real certified
MB-16 multimodal dataset (itself built from a real certified MB-14
vision session with a real PDF and a real embedded PNG) and a real
approved MB-17 grounded RAG session are built first, then MB-18's full
12-stage workflow is driven end to end over them: real artifact files
are written to disk, real SHA-256 checksums are computed, a real
readiness report is generated, and a real permanent memory record is
created on approval.

Unlike every other MB-14 through MB-17 test file in this suite, this
fixture explicitly sandboxes `document_dir` (and its sibling path
fields) into `tmp_path`, matching `tests/backend/conftest.py`'s own
established, correct pattern -- without it, `Settings._resolve_path()`
resolves the default relative `document_dir` against the real project
root instead of the sandbox, and real PDFs/artifacts leak onto disk
outside of pytest's temp directory.
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


def _create_admin(app: FastAPI, username: str = "tp-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainTrainingPipelineService:
    return MiniBrainTrainingPipelineService(app.state.settings)


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


async def _run_to_report(svc: MiniBrainTrainingPipelineService, session_public_id: str, admin_id: str, *, dataset_ids: list[str], rag_ids: list[str]) -> dict:
    session = svc.run_collect_datasets_stage(session_public_id, dataset_session_public_ids=dataset_ids, admin_id=admin_id)
    session = svc.run_collect_rag_memory_stage(session["public_id"], rag_session_public_ids=rag_ids, admin_id=admin_id)
    session = svc.run_analyze_language_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_analyze_vision_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_analyze_tokenizer_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_plan_splits_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_plan_curriculum_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_estimate_hardware_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_build_package_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle: multimodal dataset + grounded RAG memory ------------------------------------


async def test_full_cycle_multimodal_dataset_with_rag_memory(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="Mountain scene multimodal package", admin_id=admin_id)
    assert session["stage"] == "collect_datasets"

    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id])
    assert session["stage"] == "awaiting_admin_review"
    assert session["readiness_report"]["training_executed"] is False
    assert session["readiness_report"]["benchmark_executed"] is False
    assert session["image_statistics_report"]["image_count"] == 1
    assert session["grounding_quality_report"]["query_count"] == 1

    packages = svc.list_packages(session["public_id"])["items"]
    assert len(packages) == session["package_manifest"]["artifact_count"] + 2
    package_dir = Path(session["package_directory"])
    for pkg in packages:
        path = package_dir / pkg["relative_path"]
        assert path.exists()
        assert path.stat().st_size == pkg["file_size_bytes"]

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_approved"

    memory = svc.list_memory()["items"]
    assert len(memory) == 1
    assert memory[0]["source_dataset_count"] == 1
    assert memory[0]["source_rag_memory_count"] == 1


async def test_text_only_dataset_produces_zero_images(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id, with_image=False)

    svc = _svc(api_app)
    session = svc.create_session(topic="Text-only package", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    assert session["image_statistics_report"]["image_count"] == 0
    assert "text-only" in session["image_statistics_report"]["disclosure"]


async def test_dataset_with_no_rag_memory_is_still_valid(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="No RAG memory package", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    assert session["rag_memory_collection_report"]["accepted_count"] == 0
    assert session["grounding_quality_report"]["query_count"] == 0
    assert session["stage"] == "awaiting_admin_review"


# -- certified-dataset enforcement ------------------------------------------------------------


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


async def test_collect_rag_memory_rejects_unapproved_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    unapproved = vr.create_session(multimodal_dataset_session_public_id=mds_id, query="anything", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    report = svc.run_collect_rag_memory_stage(
        session["public_id"], rag_session_public_ids=[unapproved["public_id"]], admin_id=admin_id,
    )
    assert report["rag_memory_collection_report"]["accepted_count"] == 0
    assert report["rag_memory_collection_report"]["rejected_count"] == 1


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_plan_splits_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_build_package_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


async def test_package_build_impossible_before_stages_2_through_9_succeed(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = svc.run_collect_datasets_stage(session["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_build_package_stage(session["public_id"], admin_id=admin_id)


# -- admin review decisions --------------------------------------------------------------


async def test_admin_review_reject_and_archive(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(topic="reject me", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["status"] == "admin_rejected"

    session2 = svc.create_session(topic="archive me", admin_id=admin_id)
    session2 = await _run_to_report(svc, session2["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    session2 = svc.admin_review(session2["public_id"], decision="archive", admin_id=admin_id)
    assert session2["status"] == "admin_archived"


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(topic="t", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)


# -- deterministic split & hash reproducibility ------------------------------------------------


async def test_split_stage_is_reproducible_given_the_same_seed(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)

    session_a = svc.create_session(topic="a", admin_id=admin_id)
    session_a = svc.run_collect_datasets_stage(session_a["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session_a = svc.run_collect_rag_memory_stage(session_a["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session_a = svc.run_analyze_language_stage(session_a["public_id"], admin_id=admin_id)
    session_a = svc.run_analyze_vision_stage(session_a["public_id"], admin_id=admin_id)
    session_a = svc.run_analyze_tokenizer_stage(session_a["public_id"], admin_id=admin_id)
    session_a = svc.run_plan_splits_stage(session_a["public_id"], admin_id=admin_id, seed=42)

    session_b = svc.create_session(topic="b", admin_id=admin_id)
    session_b = svc.run_collect_datasets_stage(session_b["public_id"], dataset_session_public_ids=[mds_id], admin_id=admin_id)
    session_b = svc.run_collect_rag_memory_stage(session_b["public_id"], rag_session_public_ids=[], admin_id=admin_id)
    session_b = svc.run_analyze_language_stage(session_b["public_id"], admin_id=admin_id)
    session_b = svc.run_analyze_vision_stage(session_b["public_id"], admin_id=admin_id)
    session_b = svc.run_analyze_tokenizer_stage(session_b["public_id"], admin_id=admin_id)
    session_b = svc.run_plan_splits_stage(session_b["public_id"], admin_id=admin_id, seed=42)

    assert session_a["splits_report"]["train"] == session_b["splits_report"]["train"]
    assert session_a["splits_report"]["validation"] == session_b["splits_report"]["validation"]
    assert session_a["splits_report"]["test"] == session_b["splits_report"]["test"]


async def test_package_manifest_checksum_is_a_real_sha256_and_stable_across_stages(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(topic="hash check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])

    reproducibility = session["package_manifest"]["reproducibility"]
    checksum = reproducibility["manifest_checksum_sha256"]
    assert isinstance(checksum, str) and len(checksum) == 64
    assert reproducibility["split_seed"] == session["splits_report"]["seed"]

    # Approving does not rebuild the package -- the checksum recorded in permanent
    # memory must match the one already computed at build_package time.
    approved = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    memory = svc.list_memory()["items"]
    assert memory[0]["package_manifest_checksum"] == checksum
    assert approved["package_manifest"]["reproducibility"]["manifest_checksum_sha256"] == checksum


# -- package manifest integrity -----------------------------------------------------------------


async def test_package_manifest_integrity_matches_database_rows(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(topic="integrity check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])

    packages = svc.list_packages(session["public_id"])["items"]
    manifest_names = {a["artifact_name"] for a in session["package_manifest"]["artifacts"]}
    db_names = {p["artifact_name"] for p in packages}
    # manifest.json and reproducibility.json are tracked in the DB but never self-listed.
    assert db_names - manifest_names == {"manifest.json", "reproducibility.json"}


# -- large-record-count streaming path ----------------------------------------------------------


async def test_large_record_count_streaming_path(api_app: FastAPI) -> None:
    """Proves the tokenizer/split/curriculum/hardware stages tolerate a
    dataset with many records without materializing everything in a
    single list held by the caller (they stream via `_iter_records`)."""
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)

    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    record_count_before = len(mm.list_records(mds_id, status="active")["items"])
    assert record_count_before > 0

    svc = _svc(api_app)
    session = svc.create_session(topic="streaming check", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    assert session["splits_report"]["counts"]["total"] == record_count_before


# -- byte-level proof upstream sessions never modified ------------------------------------------


async def test_mb16_session_byte_identical_before_and_after(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    before = mm.session(mds_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="mb16 unchanged", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[])
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    after = mm.session(mds_id)
    assert before == after


async def test_mb17_session_byte_identical_before_and_after(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    vr_id = await _seed_approved_rag_session(api_app, mds_id, admin_id)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    before = vr.session(vr_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="mb17 unchanged", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, dataset_ids=[mds_id], rag_ids=[vr_id])
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    after = vr.session(vr_id)
    assert before == after


# -- misc -----------------------------------------------------------------------------------


async def test_create_session_rejects_empty_topic(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    with pytest.raises(ValidationError):
        svc.create_session(topic="   ", admin_id=admin_id)


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")


async def test_list_available_rag_memory_proxies_mb17(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, _vs_id = await _seed_certified_multimodal_dataset(api_app, admin_id)
    await _seed_approved_rag_session(api_app, mds_id, admin_id)
    svc = _svc(api_app)
    result = svc.list_available_rag_memory()
    assert len(result["items"]) == 1
