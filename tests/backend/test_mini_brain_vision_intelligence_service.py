"""MB-14: service-level tests for MiniBrainVisionIntelligenceService
against a real, seeded temp database -- no mocks. A real PDF with a
real embedded PNG image is built via PyMuPDF, uploaded and processed
through Document Workspace's own real pipeline, then MB-14's full
14-stage workflow is driven end to end over it.
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
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)

pytestmark = pytest.mark.anyio


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


def _create_admin(app: FastAPI, username: str = "vi-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainVisionIntelligenceService:
    return MiniBrainVisionIntelligenceService(app.state.settings)


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


def _make_pdf_with_image(text: str = "Mountain River Fish Tree scene page one.") -> bytes:
    png_image = Image.new("RGB", (200, 150), color=(120, 130, 140))
    buffer = BytesIO()
    png_image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
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


def _run_stages_through_annotation(svc, session_public_id: str, admin_id: str) -> dict:
    session = svc.run_image_extraction_stage(session_public_id, admin_id=admin_id)
    session = svc.run_image_quality_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_vision_understanding_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_cross_validation_stage(
        session["public_id"], admin_id=admin_id, dataset_text="Mountain River Fish Tree scene page one.",
    )
    session = svc.run_caption_stage(session["public_id"], admin_id=admin_id, admin_caption="A mountain scene.")
    session = svc.run_bounding_box_stage(session["public_id"], admin_id=admin_id)
    return session


def _run_all_stages(svc, session_public_id: str, admin_id: str) -> dict:
    session = _run_stages_through_annotation(svc, session_public_id, admin_id)
    objects = svc.list_objects(session["public_id"], status="active")["items"]
    unknown_object = objects[0]
    svc.annotate(
        session["public_id"], action="rename", object_public_id=unknown_object["public_id"],
        payload={"label": "Mountain"}, admin_id=admin_id,
    )
    svc.annotate(
        session["public_id"], action="redraw_box", object_public_id=unknown_object["public_id"],
        payload={"bounding_box": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}}, admin_id=admin_id,
    )
    image_public_id = svc.list_images(session["public_id"])["items"][0]["public_id"]
    svc.annotate(
        session["public_id"], action="add", object_public_id=None,
        payload={
            "image_public_id": image_public_id, "label": "River", "confidence": 1.0,
            "bounding_box": {"x": 0.15, "y": 0.15, "width": 0.2, "height": 0.2},
        },
        admin_id=admin_id,
    )
    session = svc.finish_annotation_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_knowledge_graph_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_qa_generation_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_quality_score_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle with a real PDF and a real embedded image --------------------------------------


async def test_full_cycle_with_real_pdf_and_embedded_image(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    assert session["stage"] == "image_extraction"

    session = _run_all_stages(svc, session["public_id"], admin_id)
    assert session["stage"] == "awaiting_admin_review"
    assert session["vision_report"]["ready_for_admin_review"] is True

    assert session["image_extraction_report"]["total_images"] == 1
    assert session["quality_report"]["average_quality_score"] > 0
    assert session["vision_understanding_report"]["vision_model_available"] is False
    assert session["knowledge_graph_report"]["edge_count"] >= 1
    assert session["qa_report"]["question_count"] > 0
    assert session["vision_dataset_draft_report"]["verified"] is False

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "certified"
    assert session["status"] == "admin_approved"


async def test_admin_review_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)

    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


async def test_admin_review_request_fix_and_archive(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)
    session = svc.admin_review(session["public_id"], decision="request_fix", admin_id=admin_id)
    assert session["status"] == "admin_requested_fix" and session["stage"] == "closed"

    session2 = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session2 = _run_all_stages(svc, session2["public_id"], admin_id)
    session2 = svc.admin_review(session2["public_id"], decision="archive", admin_id=admin_id)
    assert session2["status"] == "admin_archived" and session2["stage"] == "closed"


async def test_admin_review_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_image_quality_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- annotation behavior -------------------------------------------------------------------


async def test_annotate_delete_is_a_soft_status_flip_not_a_row_delete(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_stages_through_annotation(svc, session["public_id"], admin_id)

    unknown_object = svc.list_objects(session["public_id"], status="active")["items"][0]
    svc.annotate(
        session["public_id"], action="delete", object_public_id=unknown_object["public_id"],
        payload={}, admin_id=admin_id,
    )

    active = svc.list_objects(session["public_id"], status="active")["items"]
    assert unknown_object["public_id"] not in {o["public_id"] for o in active}
    all_objects = svc.list_objects(session["public_id"])["items"]
    deleted = [o for o in all_objects if o["public_id"] == unknown_object["public_id"]][0]
    assert deleted["status"] == "deleted"


async def test_annotate_rejects_unknown_action(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_stages_through_annotation(svc, session["public_id"], admin_id)
    unknown_object = svc.list_objects(session["public_id"], status="active")["items"][0]

    with pytest.raises(ValidationError):
        svc.annotate(
            session["public_id"], action="teleport", object_public_id=unknown_object["public_id"],
            payload={}, admin_id=admin_id,
        )


async def test_annotate_rejects_wrong_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.annotate(session["public_id"], action="rename", object_public_id="x", payload={}, admin_id=admin_id)


# -- document is never modified, training/runtime/rag/gguf/dataset untouched --------------------


async def test_document_pdf_file_is_never_modified(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    documents = DocumentService(api_app.state.settings)
    document_before = documents.get(document_public_id)

    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    _run_all_stages(svc, session["public_id"], admin_id)

    document_after = documents.get(document_public_id)
    assert document_before["checksum_prefix"] == document_after["checksum_prefix"]


async def test_events_are_recorded_across_the_full_cycle(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    document_public_id = await _seed_document_with_image(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(document_source_public_id=document_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    events = svc.events(session["public_id"], limit=100)["items"]
    event_types = {e["event_type"] for e in events}
    assert "session_created" in event_types
    assert "images_extracted" in event_types
    assert "vision_review_approve" in event_types


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")
