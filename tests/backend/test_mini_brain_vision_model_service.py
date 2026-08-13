"""MB-15: service-level tests for MiniBrainVisionModelService against
a real, seeded temp database -- no mocks. A real MB-14 vision session
(with a real PDF and a real embedded PNG image, driven through MB-14's
own real pipeline) is built first, then MB-15's full 14-stage workflow
is driven end to end over it, including a real admin correction flow
(the honest default in this environment, since no vision model file
exists anywhere -- every provider call fails with `BackendUnavailableError`,
caught and reported, never fabricated).
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
from backend.services.mini_brain_vision_model_service import (
    MiniBrainVisionModelService,
    reset_session_backends_for_tests,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_backends():
    reset_session_backends_for_tests()
    yield
    reset_session_backends_for_tests()


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _create_admin(app: FastAPI, username: str = "vm-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainVisionModelService:
    return MiniBrainVisionModelService(app.state.settings)


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


async def _seed_mb14_session(app: FastAPI, admin_id: str) -> str:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_pdf_with_image())
    document = await documents.upload(upload_file, "embedded_text", "en", admin_id)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), admin_id)

    vi = MiniBrainVisionIntelligenceService(app.state.settings)
    session = vi.create_session(document_source_public_id=document["public_id"], admin_id=admin_id)
    session = vi.run_image_extraction_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_image_quality_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_vision_understanding_stage(session["public_id"], admin_id=admin_id)
    session = vi.run_ocr_cross_validation_stage(
        session["public_id"], admin_id=admin_id, dataset_text="Mountain River Fish Tree scene page one.",
    )
    return session["public_id"]


def _run_to_admin_review(svc: MiniBrainVisionModelService, session_public_id: str, admin_id: str) -> dict:
    session = svc.run_image_load_stage(session_public_id, admin_id=admin_id)
    session = svc.run_provider_selection_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_object_detection_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_scene_detection_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_caption_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_relationship_detection_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_cross_validation_stage(
        session["public_id"], admin_id=admin_id, dataset_text="Mountain River Fish Tree scene page one.",
    )
    session = svc.run_quality_score_stage(session["public_id"], admin_id=admin_id)
    return session


def _run_all_stages(svc: MiniBrainVisionModelService, session_public_id: str, admin_id: str) -> dict:
    session = _run_to_admin_review(svc, session_public_id, admin_id)
    images = svc.vision_intelligence.list_images(
        svc.session(session["public_id"])["vision_session_public_id"]
    )["items"]
    session = svc.review_prediction(
        session["public_id"], action="add", prediction_public_id=None,
        payload={"image_public_id": images[0]["public_id"], "label": "Mountain",
                  "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
        admin_id=admin_id,
    )
    session = svc.finish_admin_review_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_correction_memory_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_knowledge_graph_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle -----------------------------------------------------------------------


async def test_full_cycle_with_real_mb14_session_and_honest_unavailable_provider(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="llava_gguf_cpu", admin_id=admin_id,
    )
    assert session["stage"] == "image_load"

    session = _run_all_stages(svc, session["public_id"], admin_id)
    assert session["stage"] == "awaiting_admin_review"
    assert session["vision_report"]["ready_for_admin_review"] is True
    assert session["detection_report"]["provider_available"] is False
    assert session["provider_report"]["backend_library_available"] is True
    assert session["provider_report"]["model_loaded"] is False

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "certified"
    assert session["status"] == "admin_approved"

    memory = svc.list_learning_memory()["items"]
    assert len(memory) == 1
    assert memory[0]["total_predictions"] == 1
    assert memory[0]["corrected_count"] == 0


async def test_admin_review_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    session = _run_all_stages(svc, session["public_id"], admin_id)

    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


async def test_admin_review_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    session = _run_all_stages(svc, session["public_id"], admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)


# -- provider registry and selection -----------------------------------------------------


async def test_provider_registry_seeded_with_six_providers(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    providers = svc.list_providers()["items"]
    assert len(providers) == 6
    active = {p["provider_key"] for p in providers if p["status"] == "active"}
    assert active == {"onnx_cpu", "openvino_cpu", "llava_gguf_cpu"}


async def test_set_provider_status_toggles_registry(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    svc.set_provider_status("onnx_cpu", status="inactive", admin_id=admin_id)
    providers = svc.list_providers(status="inactive")["items"]
    assert any(p["provider_key"] == "onnx_cpu" for p in providers)


async def test_provider_selection_rejects_disabled_provider(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    svc.set_provider_status("onnx_cpu", status="inactive", admin_id=admin_id)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    svc.run_image_load_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_provider_selection_stage(session["public_id"], admin_id=admin_id)


async def test_provider_selection_with_nonexistent_model_path_is_honest(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="llava_gguf_cpu", admin_id=admin_id,
    )
    svc.run_image_load_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_provider_selection_stage(
        session["public_id"], admin_id=admin_id, model_path="/nonexistent/vision.gguf",
        mmproj_path="/nonexistent/mmproj.gguf",
    )
    assert session["provider_report"]["model_loaded"] is False
    assert "does not exist" in session["provider_report"]["load_error"]


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )

    with pytest.raises(ValidationError):
        svc.run_object_detection_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- admin review actions -----------------------------------------------------------------


async def test_review_add_and_split_flow(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    session = _run_to_admin_review(svc, session["public_id"], admin_id)

    images = svc.vision_intelligence.list_images(vision_session_public_id)["items"]
    session = svc.review_prediction(
        session["public_id"], action="add", prediction_public_id=None,
        payload={"image_public_id": images[0]["public_id"], "label": "Region",
                  "bounding_box": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}},
        admin_id=admin_id,
    )
    added = svc.list_predictions(session["public_id"])["items"][0]

    session = svc.review_prediction(
        session["public_id"], action="split", prediction_public_id=added["public_id"],
        payload={"new_predictions": [
            {"label": "Left", "bounding_box": {"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}},
            {"label": "Right", "bounding_box": {"x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0}},
        ]},
        admin_id=admin_id,
    )
    predictions = svc.list_predictions(session["public_id"])["items"]
    labels_by_status = {p["review_status"] for p in predictions}
    assert "split" in labels_by_status
    assert {"Left", "Right"} <= {p["label"] for p in predictions}

    corrections = svc.list_corrections(session["public_id"])["items"]
    assert any(c["action"] == "split" for c in corrections)


async def test_review_rejects_wrong_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    with pytest.raises(ValidationError):
        svc.review_prediction(session["public_id"], action="approve", prediction_public_id="x", payload={}, admin_id=admin_id)


async def test_review_rejects_unknown_action(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    session = _run_to_admin_review(svc, session["public_id"], admin_id)
    with pytest.raises(ValidationError):
        svc.review_prediction(session["public_id"], action="teleport", prediction_public_id=None, payload={}, admin_id=admin_id)


# -- MB-14 and document are never modified --------------------------------------------------


async def test_mb14_session_is_never_modified(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    vision_session_public_id = await _seed_mb14_session(api_app, admin_id)
    vi = MiniBrainVisionIntelligenceService(api_app.state.settings)
    before = vi.session(vision_session_public_id)

    svc = _svc(api_app)
    session = svc.create_session(
        vision_session_public_id=vision_session_public_id, provider_key="onnx_cpu", admin_id=admin_id,
    )
    session = _run_all_stages(svc, session["public_id"], admin_id)
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    after = vi.session(vision_session_public_id)
    assert before == after


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")


async def test_create_session_requires_a_real_mb14_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    with pytest.raises(NotFoundError):
        svc.create_session(vision_session_public_id="does-not-exist", provider_key="onnx_cpu", admin_id=admin_id)
