"""MB-13: service-level tests for MiniBrainLanguageIntelligenceService
against a real, seeded temp database -- no mocks. A real dataset
source with real Tamil/English/Tanglish/OCR-error records and a real
admin-activated Tamil correction rule (via the existing Document Tamil
Correction Registry) are built first, then MB-13's full 12-stage
workflow is driven end to end over them.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from backend.services.document_tamil_correction_registry_service import (
    DocumentTamilCorrectionRegistryService,
)
from backend.services.mini_brain_language_intelligence_service import (
    MiniBrainLanguageIntelligenceService,
)

pytestmark = pytest.mark.anyio

TAMIL_TEXTS = [
    "தமிழ் மொழி மிகவும் பழமையான மொழிகளில் ஒன்றாகும். இது இந்தியாவின் தமிழ்நாடு மாநிலத்தில் பேசப்படுகிறது.",
    "இது ஒரு சோதனை வாக்கியம் ொ்.",
    "epadi irukku nga, ellam nalla iruka?",
    "குறுகிய பதில்.",
    "இது இந்தியாவின் ஒரு பகுதி, தமிழ்நாடு என அழைக்கப்படுகிறது.",
]


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


def _create_admin(app: FastAPI, username: str = "li-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainLanguageIntelligenceService:
    return MiniBrainLanguageIntelligenceService(app.state.settings)


def _seed_dataset_source(app: FastAPI, admin_id: str) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="LI Set", language="ta", source_type="manual"), admin_id,
    )
    for text in TAMIL_TEXTS:
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="ta",
                instruction="கேள்வி", output_text=text, metadata={},
            ),
            admin_id,
        )
    return source["public_id"]


def _seed_active_correction_rule(app: FastAPI, admin_id: str) -> None:
    registry = DocumentTamilCorrectionRegistryService(app.state.settings)
    rule = registry.create_rule(
        incorrect_form="சோதனை", approved_correction="சோதனா", issue_category="spelling_variant",
        evidence="scanner artefact", confidence_band="medium", meaning_change_risk="mechanical", admin_id=admin_id,
    )
    registry.transition(rule["public_id"], "submit_review", admin_id)
    registry.transition(rule["public_id"], "approve", admin_id)
    registry.transition(rule["public_id"], "activate", admin_id)


def _run_all_stages(svc: MiniBrainLanguageIntelligenceService, session_public_id: str, admin_id: str) -> dict:
    session = svc.run_language_scan_stage(session_public_id, admin_id=admin_id)
    session = svc.run_unicode_validation_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_spell_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_grammar_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_tanglish_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_translation_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_quality_score_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


# -- full cycle with real evidence ----------------------------------------------------------


async def test_full_cycle_with_real_correction_registry_evidence(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    _seed_active_correction_rule(api_app, admin_id)

    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    assert session["stage"] == "language_scan"

    session = _run_all_stages(svc, session["public_id"], admin_id)
    assert session["stage"] == "awaiting_admin_review"
    assert session["language_report"]["ready_for_admin_review"] is True

    assert session["language_scan_report"]["dominant_language"] == "tamil"
    assert session["spell_report"]["match_count"] > 0
    assert session["ocr_report"]["possible_correction_count"] > 0
    assert session["tanglish_report"]["forward"]["tanglish_record_count"] > 0
    assert session["dataset_draft_report"]["applicable"] is True
    assert session["dataset_draft_report"]["english_draft"] is None

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "certified"
    assert session["status"] == "admin_approved"


async def test_admin_review_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)

    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


async def test_admin_review_request_fix_and_archive(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)
    session = svc.admin_review(session["public_id"], decision="request_fix", admin_id=admin_id)
    assert session["status"] == "admin_requested_fix" and session["stage"] == "closed"

    session2 = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session2 = _run_all_stages(svc, session2["public_id"], admin_id)
    session2 = svc.admin_review(session2["public_id"], decision="archive", admin_id=admin_id)
    assert session2["status"] == "admin_archived" and session2["stage"] == "closed"


async def test_admin_review_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="bogus", admin_id=admin_id)


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_spell_analysis_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.generate_report_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


async def test_translation_analysis_with_explicit_pairs(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_language_scan_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_unicode_validation_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_spell_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_grammar_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_ocr_analysis_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_tanglish_analysis_stage(session["public_id"], admin_id=admin_id)

    session = svc.run_translation_analysis_stage(
        session["public_id"], admin_id=admin_id,
        pairs=[{"tamil_text": "இது 5 பொருட்கள்.", "english_text": "This has 10 items."}],
    )
    assert session["translation_report"]["pairs_analyzed"] == 1
    assert session["translation_report"]["terminology_consistency_issues"]


# -- dataset never written, source untouched --------------------------------------------------


async def test_dataset_records_are_never_modified(api_app: FastAPI) -> None:
    import sqlite3

    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        before = conn.execute("SELECT output_text, updated_at FROM dataset_records ORDER BY id").fetchall()

    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = _run_all_stages(svc, session["public_id"], admin_id)
    svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)

    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        after = conn.execute("SELECT output_text, updated_at FROM dataset_records ORDER BY id").fetchall()
    assert before == after


# -- events + listing --------------------------------------------------------------------------


async def test_events_are_recorded_append_only_and_readable(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    svc.run_language_scan_stage(session["public_id"], admin_id=admin_id)
    events = svc.events(session["public_id"])["items"]
    assert len(events) == 2
    assert events[-1]["event_type"] == "session_created"


async def test_list_sessions_returns_created_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    listed = svc.list_sessions()["items"]
    assert any(s["public_id"] == session["public_id"] for s in listed)
