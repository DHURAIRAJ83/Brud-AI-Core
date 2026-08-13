"""MB-21: service-level tests for MiniBrainExternalAiGatewayService
against a real, seeded temp database -- no mocks except for
`MockProviderClient`, which is the task spec's own required test
double (no real network call is ever made in this test file). Real
certified MB-16 datasets and real approved MB-17 grounded RAG sessions
are built first, then MB-21's full 12-stage workflow is driven end to
end over them with two mock providers: authorization is enforced,
prompts are sanitized, providers are dispatched, agreement is
analyzed, evidence is bundled, a report is generated, and the session
is reviewed and archived.
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
from backend.services.external_ai_provider_client import MockProviderClient
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
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


def _create_admin(app: FastAPI, username: str = "ga-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI, provider_clients: dict) -> MiniBrainExternalAiGatewayService:
    return MiniBrainExternalAiGatewayService(app.state.settings, provider_clients=provider_clients)


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


async def _seed_certified_dataset_and_rag(app: FastAPI, admin_id: str) -> tuple[str, str]:
    documents = DocumentService(app.state.settings)
    upload_file = _FakeUploadFile("scene.pdf", _make_text_only_pdf())
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
    session = mm.admin_review(mds_id, decision="approve", admin_id=admin_id)
    assert session["status"] == "admin_approved"

    vr = MiniBrainVisionRagService(app.state.settings)
    vr_session = vr.create_session(multimodal_dataset_session_public_id=mds_id, query="Where is the river located?", admin_id=admin_id)
    vr_id = vr_session["public_id"]
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

    return mds_id, vr_id


async def _run_to_report(svc: MiniBrainExternalAiGatewayService, session_public_id: str, admin_id: str, *, provider_keys: list[str], admin_stated_need: str = "") -> dict:
    session = svc.run_validate_authorization_stage(session_public_id, authorization_note="test authorization", admin_id=admin_id)
    session = svc.run_sanitize_inputs_stage(session["public_id"], admin_stated_need=admin_stated_need, admin_id=admin_id)
    session = svc.run_select_providers_stage(session["public_id"], requested_provider_keys=provider_keys, admin_id=admin_id)
    session = svc.run_dispatch_requests_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_collect_responses_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_normalize_responses_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_analyze_agreement_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_build_evidence_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle: public-style evaluation with two mock providers ------------------------------------


async def test_full_cycle_public_evaluation_two_providers(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, vr_id = await _seed_certified_dataset_and_rag(api_app, admin_id)

    mock1 = MockProviderClient(provider_key="mock1", canned_text="The river flows through the mountain valley near the trees.")
    mock2 = MockProviderClient(provider_key="mock2", canned_text="The river flows through a mountain valley with trees nearby.")
    svc = _svc(api_app, {"mock1": mock1, "mock2": mock2})

    session = svc.create_session(
        topic="public eval", purpose="public_style_stress_test", admin_id=admin_id,
        dataset_session_public_ids=[mds_id], rag_session_public_id=vr_id,
    )
    assert session["stage"] == "validate_authorization"

    session = await _run_to_report(svc, session["public_id"], admin_id, provider_keys=["mock1", "mock2"])
    assert session["stage"] == "awaiting_admin_review"
    assert session["gateway_report"]["external_ai_output_unverified"] is True
    assert session["agreement_report"]["agreement"]["successful_provider_count"] == 2

    runs = svc.list_provider_runs(session["public_id"])["items"]
    assert len(runs) == 2
    assert all(r["status"] == "success" for r in runs)

    session = svc.admin_review(session["public_id"], decision="accept", admin_id=admin_id)
    assert session["stage"] == "reviewed"
    assert session["status"] == "admin_accepted"

    session = svc.archive(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "archived"
    assert session["status"] == "archived"

    memory = svc.list_memory()["items"]
    assert len(memory) == 1
    assert memory[0]["successful_provider_count"] == 2


# -- data acquisition mode -------------------------------------------------------------------------


async def test_data_acquisition_mode_handoff_never_inserts(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock1 = MockProviderClient(provider_key="mock1", canned_text="Fact: rivers erode rock over time. Example: the Grand Canyon. No reference known with certainty.")
    svc = _svc(api_app, {"mock1": mock1})

    session = svc.create_session(topic="river erosion data", purpose="data_acquisition_assistance", admin_id=admin_id)
    session = await _run_to_report(
        svc, session["public_id"], admin_id, provider_keys=["mock1"], admin_stated_need="missing facts about river erosion",
    )
    assert session["stage"] == "awaiting_admin_review"
    next_actions = session["gateway_report"]["recommended_next_actions"]
    assert any("Dataset Studio" in action for action in next_actions)

    session = svc.admin_review(session["public_id"], decision="needs_followup", admin_id=admin_id)
    assert session["status"] == "admin_needs_followup"
    svc.archive(session["public_id"], admin_id=admin_id)


# -- authorization required ----------------------------------------------------------------------


async def test_authorization_required_before_any_other_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app, {"mock1": MockProviderClient(provider_key="mock1")})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_sanitize_inputs_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_select_providers_stage(session["public_id"], requested_provider_keys=["mock1"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_dispatch_requests_stage(session["public_id"], admin_id=admin_id)


async def test_authorization_rejects_empty_note(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app, {})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_validate_authorization_stage(session["public_id"], authorization_note="   ", admin_id=admin_id)


# -- provider disabled / unavailable / timeout paths --------------------------------------------


async def test_provider_disabled_path_is_skipped_not_selected(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock_disabled = MockProviderClient(provider_key="mock_disabled", available=False)
    mock_enabled = MockProviderClient(provider_key="mock_enabled", canned_text="hello")
    svc = _svc(api_app, {"mock_disabled": mock_disabled, "mock_enabled": mock_enabled})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    session = svc.run_validate_authorization_stage(session["public_id"], authorization_note="test", admin_id=admin_id)
    session = svc.run_sanitize_inputs_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_select_providers_stage(session["public_id"], requested_provider_keys=["mock_disabled", "mock_enabled"], admin_id=admin_id)
    assert session["provider_selection_report"]["selected_count"] == 1
    assert session["provider_selection_report"]["selected_providers"][0]["provider_key"] == "mock_enabled"


async def test_select_providers_fails_when_none_enabled(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock_disabled = MockProviderClient(provider_key="mock_disabled", available=False)
    svc = _svc(api_app, {"mock_disabled": mock_disabled})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    session = svc.run_validate_authorization_stage(session["public_id"], authorization_note="test", admin_id=admin_id)
    session = svc.run_sanitize_inputs_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.run_select_providers_stage(session["public_id"], requested_provider_keys=["mock_disabled"], admin_id=admin_id)


async def test_provider_timeout_path_recorded_as_failure(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock_timeout = MockProviderClient(provider_key="mock_timeout", status="timeout", latency_ms=500.0)
    mock_ok = MockProviderClient(provider_key="mock_ok", canned_text="a working response")
    svc = _svc(api_app, {"mock_timeout": mock_timeout, "mock_ok": mock_ok})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, provider_keys=["mock_timeout", "mock_ok"])
    assert session["agreement_report"]["failures"]["failure_count"] == 1
    assert session["agreement_report"]["agreement"]["failed_provider_count"] == 1
    assert session["agreement_report"]["agreement"]["successful_provider_count"] == 1


# -- contradiction detection ------------------------------------------------------------------------


async def test_contradiction_detected_between_dissimilar_providers(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock1 = MockProviderClient(provider_key="mock1", canned_text="apples grow on trees in orchards near farms")
    mock2 = MockProviderClient(provider_key="mock2", canned_text="quantum entanglement links distant particles instantly")
    svc = _svc(api_app, {"mock1": mock1, "mock2": mock2})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, provider_keys=["mock1", "mock2"])
    assert session["agreement_report"]["agreement"]["contradiction_count"] == 1


# -- privacy sanitization --------------------------------------------------------------------------


async def test_sanitization_redacts_secret_from_admin_stated_need(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app, {})
    session = svc.create_session(topic="t", purpose="data_acquisition_assistance", admin_id=admin_id)
    session = svc.run_validate_authorization_stage(session["public_id"], authorization_note="test", admin_id=admin_id)
    session = svc.run_sanitize_inputs_stage(
        session["public_id"], admin_stated_need="my api_key=sk-98765 leaked, please help find replacement data", admin_id=admin_id,
    )
    assert "sk-98765" not in session["sanitization_report"]["sanitized_prompt"]


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app, {})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_analyze_agreement_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="accept", admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.archive(session["public_id"], admin_id=admin_id)


# -- byte-level proofs upstream sessions never modified ------------------------------------------


async def test_mb16_and_mb17_byte_identical_before_and_after(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mds_id, vr_id = await _seed_certified_dataset_and_rag(api_app, admin_id)

    mm = MiniBrainMultimodalDatasetGeneratorService(api_app.state.settings)
    vr = MiniBrainVisionRagService(api_app.state.settings)
    mds_before = mm.session(mds_id)
    vr_before = vr.session(vr_id)

    mock1 = MockProviderClient(provider_key="mock1", canned_text="a response")
    svc = _svc(api_app, {"mock1": mock1})
    session = svc.create_session(
        topic="unmodified check", purpose="public_style_stress_test", admin_id=admin_id,
        dataset_session_public_ids=[mds_id], rag_session_public_id=vr_id,
    )
    session = await _run_to_report(svc, session["public_id"], admin_id, provider_keys=["mock1"])
    svc.admin_review(session["public_id"], decision="accept", admin_id=admin_id)
    svc.archive(session["public_id"], admin_id=admin_id)

    assert mm.session(mds_id) == mds_before
    assert vr.session(vr_id) == vr_before


async def test_unknown_session_raises_not_found(api_app: FastAPI) -> None:
    svc = _svc(api_app, {})
    with pytest.raises(NotFoundError):
        svc.session("does-not-exist")


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mock1 = MockProviderClient(provider_key="mock1", canned_text="a response")
    svc = _svc(api_app, {"mock1": mock1})
    session = svc.create_session(topic="t", purpose="public_style_stress_test", admin_id=admin_id)
    session = await _run_to_report(svc, session["public_id"], admin_id, provider_keys=["mock1"])
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)
