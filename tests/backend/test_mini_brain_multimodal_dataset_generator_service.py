"""MB-16: service-level tests for
MiniBrainMultimodalDatasetGeneratorService against a real, seeded temp
database -- no mocks. A real MB-14 vision session (itself built from a
real PDF with a real embedded PNG, driven all the way to certified) is
built first, then MB-16's full 12-stage workflow is driven end to end
over it, plus the draft-lifecycle actions (export/split/merge/delete).
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
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)

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
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _create_admin(app: FastAPI, username: str = "md-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainMultimodalDatasetGeneratorService:
    return MiniBrainMultimodalDatasetGeneratorService(app.state.settings)


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


async def _seed_certified_mb14_session(app: FastAPI, admin_id: str, *, with_image: bool = True) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    pdf_bytes = _make_pdf_with_image() if with_image else _make_text_only_pdf()
    upload_file = _FakeUploadFile("scene.pdf", pdf_bytes)
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    session = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    session = vi.run_image_extraction_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_image_quality_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_vision_understanding_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_ocr_cross_validation_stage(session["public_id"], admin_id=admin_id, dataset_text=TEXT)
    session = vi.run_caption_stage(session["public_id"], admin_id=admin_id, admin_caption="A mountain scene with a river.")
    session = vi.run_bounding_box_stage(session["public_id"], admin_id=admin_id)
    if with_image:
        objects = vi.list_objects(session["public_id"], status="active")["items"]
        vi.annotate(session["public_id"], action="rename", object_public_id=objects[0]["public_id"], payload={"label": "Mountain"}, admin_id=admin_id)
        vi.annotate(session["public_id"], action="redraw_box", object_public_id=objects[0]["public_id"], payload={"bounding_box": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}}, admin_id=admin_id)
        image_public_id = vi.list_images(session["public_id"])["items"][0]["public_id"]
        vi.annotate(
            session["public_id"], action="add", object_public_id=None,
            payload={
                "image_public_id": image_public_id, "label": "River", "confidence": 1.0,
                "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
            },
            admin_id=admin_id,
        )
    session = vi.finish_annotation_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_knowledge_graph_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_qa_generation_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_quality_score_stage(session["public_id"], admin_id=admin_id)
    session = vi.generate_report_stage(session["public_id"], admin_id=admin_id)
    session = vi.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "certified"
    return document["public_id"], session["public_id"]


def _run_to_admin_review(svc: MiniBrainMultimodalDatasetGeneratorService, session_public_id: str, admin_id: str) -> dict:
    session = svc.run_collect_sources_stage(session_public_id, admin_id=admin_id)
    session = svc.run_collect_text_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_collect_images_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_merge_metadata_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_conversation_builder_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_instruction_builder_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_quality_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_duplicate_detection_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle -----------------------------------------------------------------------


async def test_full_cycle_with_real_multimodal_document(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(
        document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id,
        admin_id=admin_id,
    )
    assert session["stage"] == "collect_sources"

    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    assert session["stage"] == "awaiting_admin_review"
    assert session["dataset_report"]["ready_for_admin_review"] is True
    assert session["metadata_report"]["is_multimodal"] is True

    records = svc.list_records(session["public_id"])["items"]
    assert len(records) > 0
    assert all(r["verified"] is False for r in records)
    record_types = {r["record_type"] for r in records}
    assert record_types == {"conversation", "instruction", "qa", "caption", "vision", "grounding", "reasoning", "training"}

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "certified"
    assert session["status"] == "admin_approved"

    memory = svc.list_memory()["items"]
    assert len(memory) == 1
    assert memory[0]["total_records"] == len(records)


async def test_text_only_document_has_no_image_records(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id, with_image=False)

    svc = _svc(api_app)
    session = svc.create_session(
        document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id,
        admin_id=admin_id,
    )
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    assert session["metadata_report"]["is_multimodal"] is False

    records = svc.list_records(session["public_id"])["items"]
    record_types = {r["record_type"] for r in records}
    assert "vision" not in record_types
    assert "grounding" not in record_types
    assert "instruction" in record_types


async def test_document_without_any_linked_session_still_generates_a_text_draft(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    documents = DocumentService(api_app.state.settings)
    upload_file = _FakeUploadFile("plain.pdf", _make_text_only_pdf())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    assert session["stage"] == "awaiting_admin_review"
    records = svc.list_records(session["public_id"])["items"]
    assert len(records) > 0


async def test_admin_review_reject_and_request_changes(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed" and session["status"] == "admin_rejected"

    session2 = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session2 = _run_to_admin_review(svc, session2["public_id"], admin_id)
    session2 = svc.admin_review(session2["public_id"], decision="request_changes", admin_id=admin_id)
    assert session2["status"] == "admin_requested_changes"


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_collect_images_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- draft lifecycle: export/delete/split/merge ----------------------------------------------


async def test_export_draft_json_and_jsonl(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)

    export_json = svc.export_draft(session["public_id"], export_format="json")
    export_jsonl = svc.export_draft(session["public_id"], export_format="jsonl")
    assert export_json["record_count"] == export_jsonl["record_count"] > 0
    assert export_json["disclosure"].startswith("this export is a file only")

    with pytest.raises(ValidationError):
        svc.export_draft(session["public_id"], export_format="xml")


async def test_delete_draft_before_certification(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = svc.run_collect_sources_stage(session["public_id"], admin_id=admin_id)

    session = svc.delete_draft(session["public_id"], admin_id=admin_id)
    assert session["status"] == "draft_deleted"
    assert session["stage"] == "closed"


async def test_delete_draft_rejects_certified_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.delete_draft(session["public_id"], admin_id=admin_id)


async def test_split_dataset_requires_certified_parent(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.split_dataset(session["public_id"], record_public_ids=["x"], admin_id=admin_id)


async def test_split_dataset_creates_child_with_subset(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    records = svc.list_records(session["public_id"])["items"]

    child = svc.split_dataset(session["public_id"], record_public_ids=[records[0]["public_id"]], admin_id=admin_id)
    assert child["parent_session_public_id"] == session["public_id"]
    assert child["stage"] == "report"
    assert len(svc.list_records(child["public_id"])["items"]) == 1


async def test_merge_datasets_requires_all_certified(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session_a = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session_a = _run_to_admin_review(svc, session_a["public_id"], admin_id)
    session_a = svc.admin_review(session_a["public_id"], decision="approve", admin_id=admin_id)

    session_b = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.merge_datasets([session_a["public_id"], session_b["public_id"]], admin_id=admin_id)


async def test_merge_datasets_combines_records(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session_a = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session_a = _run_to_admin_review(svc, session_a["public_id"], admin_id)
    session_a = svc.admin_review(session_a["public_id"], decision="approve", admin_id=admin_id)

    session_b = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session_b = _run_to_admin_review(svc, session_b["public_id"], admin_id)
    session_b = svc.admin_review(session_b["public_id"], decision="approve", admin_id=admin_id)

    records_a = len(svc.list_records(session_a["public_id"])["items"])
    records_b = len(svc.list_records(session_b["public_id"])["items"])

    merged = svc.merge_datasets([session_a["public_id"], session_b["public_id"]], admin_id=admin_id)
    assert merged["stage"] == "report"
    assert len(svc.list_records(merged["public_id"])["items"]) == records_a + records_b


# -- MB-14 and document are never modified --------------------------------------------------


async def test_mb14_session_and_document_never_modified(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id, vision_session_public_id = await _seed_certified_mb14_session(api_app, admin_id)
    vi = MiniBrainVisionIntelligenceService(api_app.state.settings)
    documents = DocumentService(api_app.state.settings)
    vision_before = vi.session(vision_session_public_id)
    document_before = documents.get(document_public_id)

    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, vision_session_public_id=vision_session_public_id, admin_id=admin_id)
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    vision_after = vi.session(vision_session_public_id)
    document_after = documents.get(document_public_id)
    assert vision_before == vision_after
    assert document_before["checksum_prefix"] == document_after["checksum_prefix"]


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")
