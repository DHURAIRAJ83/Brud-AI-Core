"""MB-11: service-level tests for MiniBrainDatasetEvolutionService
against a real, seeded temp database -- no mocks. A real dataset
source with real records, a real closed MB-08 cycle (seeded with real
Public Chat + Knowledge Gap Registry data, run through MB-08's own
real service), a real MB-09 session, and a real MB-10 session are
built first, then MB-11's full 8-stage workflow is driven end to end
over them.
"""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
)
from backend.services.mini_brain_dataset_evolution_service import MiniBrainDatasetEvolutionService
from backend.services.mini_brain_research_center_service import MiniBrainResearchCenterService

pytestmark = pytest.mark.anyio

QUESTIONS = ["What is Python used for?", "How does TCP networking work?", "Explain machine learning basics"]


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


def _create_admin(app: FastAPI, username: str = "de-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainDatasetEvolutionService:
    return MiniBrainDatasetEvolutionService(app.state.settings)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seed_dataset_source(app: FastAPI, admin_id: str, count: int = 40) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="DE Set", language="en", source_type="manual"), admin_id,
    )
    for i in range(count):
        question = QUESTIONS[i % 3]
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="en",
                instruction=question, output_text=f"Answer number {i} about {question}, in reasonable depth.",
                metadata={"topic": "programming"},
            ),
            admin_id,
        )
    return source["public_id"]


def _seed_closed_mb08_cycle(app: FastAPI, admin_id: str) -> dict:
    settings = app.state.settings
    pc = PublicChatRoutingRepository(settings.resolved_database_path)
    kg = KnowledgeGapRepository(settings.resolved_database_path)

    for i in range(15):
        grounded = i % 3 != 0
        pc.record_event({
            "request_id": f"req-{i}", "input_hash": _hash(f"q{i}"),
            "classification_decision_public_id": None, "recommended_route": "core_model",
            "resolved_route": "core_model" if grounded else "insufficient", "route_status": "executable",
            "evidence_status": "grounded" if grounded else "model_only", "detected_language": "en",
            "answer_language": "en", "safety_status": "safe", "fallbacks_attempted": [],
            "latency_ms": 100, "error_code": None, "conversation_id": f"c-{i}",
        })
    for i in range(4):
        case = kg.create_case({
            "event_type": "knowledge_gap", "primary_reason_code": "rag_content_missing",
            "reason_codes": ["rag_content_missing"], "language": "en", "domain": "History",
            "intent": "facts", "freshness": "static", "input_hash": _hash(f"case{i}"),
            "canonical_question": f"deep question {i}", "content_unavailable_for_review": False,
        })
        kg.update_case_priority(
            case["public_id"], priority_score=25.0, priority_band="high", priority_reason_codes=["frequency_weighted"],
        )

    svc = MiniBrainContinuousLearningService(settings)
    session = svc.create_session(cycle_window_days=30, admin_id=admin_id)
    session = svc.collect_feedback_stage(session["public_id"], admin_id=admin_id)
    session = svc.analyze_failures_stage(session["public_id"], admin_id=admin_id)
    session = svc.analyze_hallucinations_stage(session["public_id"], admin_id=admin_id)
    session = svc.analyze_knowledge_gaps_stage(session["public_id"], admin_id=admin_id)
    session = svc.detect_weak_topics_stage(session["public_id"], admin_id=admin_id)
    session = svc.analyze_difficulty_stage(session["public_id"], admin_id=admin_id)
    session = svc.recommend_datasets_stage(session["public_id"], admin_id=admin_id)
    session = svc.recommend_training_stage(session["public_id"], admin_id=admin_id)
    session = svc.rank_priorities_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)
    session = svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)
    return session


def _bypass_to_awaiting_rag_review(app: FastAPI, session_public_id: str) -> None:
    with sqlite3.connect(app.state.settings.resolved_database_path) as conn:
        conn.execute(
            "UPDATE mini_brain_dataset_evolution_sessions SET stage=?, rag_report_json=? WHERE public_id=?",
            (
                "awaiting_rag_review",
                json.dumps({"production_rag_readiness": "ready_for_admin_review", "coverage": 0.9}),
                session_public_id,
            ),
        )
        conn.commit()


# -- full happy path, real MB-08/MB-09/MB-10 evidence --------------------------------------


async def test_full_evolution_cycle_with_real_mb08_mb09_mb10_evidence(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    mb08_session = _seed_closed_mb08_cycle(api_app, admin_id)
    assert mb08_session["stage"] == "closed"
    assert "History" in mb08_session["continuous_learning_report"]["weak_areas"]

    planning_center = MiniBrainContinuousLearningCenterService(api_app.state.settings)
    planning_center.create_session(admin_id=admin_id)

    research_center = MiniBrainResearchCenterService(api_app.state.settings)
    research_session = research_center.create_session(topic="History", admin_id=admin_id)
    research_center.prepare_research_request_stage(research_session["public_id"], admin_id=admin_id)
    research_center.select_mode_stage(research_session["public_id"], mode="local_draft", admin_id=admin_id)
    research_center.build_local_draft_stage(research_session["public_id"], admin_id=admin_id)
    research_center.build_dataset_draft_stage(research_session["public_id"], admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    assert session["stage"] == "knowledge_evolution"

    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "dataset_evolution"
    assert "History" in session["evolution_analysis"]["weak_domains"]
    assert session["evolution_analysis"]["research_drafts_available"] == 1

    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "evolution_simulation"
    assert session["expansion_plan"]["action"] in {
        "merge", "extend", "split", "replace", "archive", "create_new",
    }

    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "recommendation"

    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    assert session["recommendation_report"]["recommendation"] in {
        "continue_current_dataset", "expand_dataset", "split_dataset", "replace_dataset",
        "research_more", "collect_more_data", "wait", "reject",
    }

    session = svc.generate_report(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "awaiting_admin_review"
    assert session["evolution_report"]["ready_for_admin_review"] is True
    assert "History" in session["evolution_report"]["weak_areas"]

    session = svc.admin_review_evolution(session["public_id"], decision="approve_evolution", admin_id=admin_id)
    assert session["status"] == "admin_approved_evolution"
    assert session["stage"] == "awaiting_admin_review"

    session = svc.admin_review_evolution(session["public_id"], decision="send_to_rag", admin_id=admin_id)
    assert session["stage"] == "rag_evaluation"
    assert session["status"] == "admin_sent_to_rag"


async def test_send_to_rag_blocked_without_prior_approve(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError, match="must be approved"):
        svc.admin_review_evolution(session["public_id"], decision="send_to_rag", admin_id=admin_id)


async def test_admin_review_decision_maps_to_correct_status(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)

    session = svc.admin_review_evolution(session["public_id"], decision="research_more", admin_id=admin_id)
    assert session["status"] == "admin_requested_more_research"
    assert session["stage"] == "closed"


async def test_admin_review_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review_evolution(session["public_id"], decision="bogus", admin_id=admin_id)


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review_evolution(session["public_id"], decision="reject", admin_id=admin_id)


async def test_generate_report_blocked_before_recommendation(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError, match="generate the recommendation"):
        svc.generate_report(session["public_id"], admin_id=admin_id)


# -- RAG review + close (RAG generation bypassed, same precedent as MB-06/MB-10) --------------


async def test_rag_review_approve_and_reject(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)
    session = svc.admin_review_evolution(session["public_id"], decision="approve_evolution", admin_id=admin_id)
    session = svc.admin_review_evolution(session["public_id"], decision="send_to_rag", admin_id=admin_id)
    assert session["stage"] == "rag_evaluation"

    _bypass_to_awaiting_rag_review(api_app, session["public_id"])
    session = svc.admin_review_rag(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "rag_admin_approved"

    session2 = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    session2 = svc.run_knowledge_evolution_stage(session2["public_id"], admin_id=admin_id)
    session2 = svc.run_dataset_evolution_stage(session2["public_id"], admin_id=admin_id)
    session2 = svc.run_evolution_simulation_stage(session2["public_id"], admin_id=admin_id)
    session2 = svc.generate_recommendation_stage(session2["public_id"], admin_id=admin_id)
    session2 = svc.generate_report(session2["public_id"], admin_id=admin_id)
    session2 = svc.admin_review_evolution(session2["public_id"], decision="approve_evolution", admin_id=admin_id)
    session2 = svc.admin_review_evolution(session2["public_id"], decision="send_to_rag", admin_id=admin_id)
    _bypass_to_awaiting_rag_review(api_app, session2["public_id"])
    session2 = svc.admin_review_rag(session2["public_id"], decision="reject", admin_id=admin_id)
    assert session2["stage"] == "closed"
    assert session2["status"] == "rag_admin_rejected"


# -- events + listing --------------------------------------------------------------------------


async def test_events_are_recorded_append_only_and_readable(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(dataset_source_public_id=source_public_id, admin_id=admin_id)
    svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
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
