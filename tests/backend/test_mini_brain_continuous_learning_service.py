"""MB-08: service-level tests for MiniBrainContinuousLearningService
against a real, seeded temp database -- no mocks. Routing events,
feedback events, and Knowledge Gap Registry cases are seeded through
those systems' own real repository methods (the same ones production
code uses), then the full 10-stage observe-analyze-recommend cycle is
driven end to end.
"""

import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from backend.models.auth import AdminCreate
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
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


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seed(api_app: FastAPI, *, domains=("History", "History", "Math")) -> dict:
    settings = api_app.state.settings
    admin = AdminRepository(settings.resolved_database_path).create_admin(
        AdminCreate(username="mb08-admin", display_name="A", password="password12345")
    )
    pc = PublicChatRoutingRepository(settings.resolved_database_path)
    kg = KnowledgeGapRepository(settings.resolved_database_path)

    for i in range(12):
        grounded = i % 3 != 0
        pc.record_event({
            "request_id": f"req-{i}", "input_hash": _hash(f"q{i}"),
            "classification_decision_public_id": None,
            "recommended_route": "core_model",
            "resolved_route": "core_model" if grounded else "insufficient",
            "route_status": "executable", "evidence_status": "grounded" if grounded else "model_only",
            "detected_language": "en", "answer_language": "en", "safety_status": "safe",
            "fallbacks_attempted": [], "latency_ms": 100, "error_code": None, "conversation_id": f"c{i}",
        })
    for i in range(4):
        pc.record_feedback({
            "request_id": f"req-{i}", "route_used": "core_model", "answer_hash": _hash(f"a{i}"),
            "feedback_type": "thumbs_down" if i % 2 == 0 else "thumbs_up", "comment": None,
        })

    for i, domain in enumerate(domains):
        case = kg.create_case({
            "event_type": "knowledge_gap", "primary_reason_code": "rag_content_missing",
            "reason_codes": ["rag_content_missing"], "language": "en", "domain": domain,
            "intent": "facts", "freshness": "static", "input_hash": _hash(f"case{i}"),
            "canonical_question": f"question {i}", "content_unavailable_for_review": False,
        })
        kg.update_case_priority(
            case["public_id"], priority_score=20.0, priority_band="high",
            priority_reason_codes=["frequency_weighted"],
        )
        kg.update_case_handoff_eligibility(
            case["public_id"], rag_research=True, rag_trial=False, rag_reason_codes=[],
            training_assessment=True, training_reason_codes=["repeatable_language_or_reasoning_capability_failure"],
        )

    return {"admin_id": admin.public_id}


def _svc(api_app: FastAPI) -> MiniBrainContinuousLearningService:
    return MiniBrainContinuousLearningService(api_app.state.settings)


async def test_full_continuous_learning_cycle_happy_path(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)

    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    assert session["stage"] == "feedback_collection"

    session = svc.collect_feedback_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "failure_analysis"
    assert session["feedback_report"]["total_conversations_observed"] == 12

    session = svc.analyze_failures_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "hallucination_analysis"
    assert session["failure_report"]["failure_rate"] is not None

    session = svc.analyze_hallucinations_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "knowledge_gap_analysis"

    session = svc.analyze_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "weak_topic_detection"
    assert session["knowledge_gap_report"]["total_knowledge_gap_cases"] == 3

    session = svc.detect_weak_topics_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "difficulty_analysis"
    assert "History" in session["weak_topic_report"]["weak_topics"]

    session = svc.analyze_difficulty_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "dataset_recommendation"

    session = svc.recommend_datasets_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "training_recommendation"
    assert session["dataset_recommendation_report"]["recommendations"]

    session = svc.recommend_training_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "priority_ranking"
    assert session["training_recommendation_report"]["action"] in {
        "No Training", "Fine Tune", "Continue Training", "Full Retraining",
    }

    session = svc.rank_priorities_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "priority_ranking"
    assert session["priority_report"]["training_recommendation"]["priority"]

    session = svc.generate_report(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "awaiting_admin_review"
    assert session["continuous_learning_report"]["overall_health"] in {"Healthy", "Needs Attention", "At Risk"}

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=seed["admin_id"])
    assert session["stage"] == "closed"
    assert session["status"] == "admin_approved"

    # safety proof: every other system's real tables are untouched
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        kg_count = conn.execute("SELECT COUNT(*) FROM knowledge_gap_cases").fetchone()[0]
        pc_count = conn.execute("SELECT COUNT(*) FROM public_chat_routing_events").fetchone()[0]
        fb_count = conn.execute("SELECT COUNT(*) FROM public_chat_feedback_events").fetchone()[0]
        job_count = conn.execute("SELECT COUNT(*) FROM pretraining_jobs").fetchone()[0]
    assert kg_count == 3
    assert pc_count == 12
    assert fb_count == 4
    assert job_count == 0


async def test_collect_feedback_blocked_at_wrong_stage(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    svc.collect_feedback_stage(session["public_id"], admin_id=seed["admin_id"])
    with pytest.raises(ValidationError, match="not 'feedback_collection'"):
        svc.collect_feedback_stage(session["public_id"], admin_id=seed["admin_id"])


async def test_analyze_failures_blocked_before_feedback_collected(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    with pytest.raises(ValidationError, match="not 'failure_analysis'"):
        svc.analyze_failures_stage(session["public_id"], admin_id=seed["admin_id"])


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="not-a-real-decision", admin_id=seed["admin_id"])


async def test_admin_review_reject_closes_session_without_side_effects(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})
    session = svc.admin_review(session["public_id"], decision="reject", admin_id=seed["admin_id"])
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


async def test_empty_evidence_produces_healthy_report(api_app: FastAPI) -> None:
    admin = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="empty-admin", display_name="A", password="password12345")
    )
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=admin.public_id)
    session = svc.collect_feedback_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.analyze_failures_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.analyze_hallucinations_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.analyze_knowledge_gaps_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.detect_weak_topics_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.analyze_difficulty_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.recommend_datasets_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.recommend_training_stage(session["public_id"], admin_id=admin.public_id)
    assert session["training_recommendation_report"]["action"] == "No Training"
    session = svc.rank_priorities_stage(session["public_id"], admin_id=admin.public_id)
    session = svc.generate_report(session["public_id"], admin_id=admin.public_id)
    assert session["continuous_learning_report"]["overall_health"] == "Healthy"


async def test_events_are_recorded(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(cycle_window_days=30, admin_id=seed["admin_id"])
    svc.collect_feedback_stage(session["public_id"], admin_id=seed["admin_id"])
    events = svc.events(session["public_id"])
    event_types = [e["event_type"] for e in events["items"]]
    assert "session_created" in event_types
    assert "feedback_collected" in event_types
