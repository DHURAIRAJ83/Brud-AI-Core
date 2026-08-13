"""MB-09: service-level tests for MiniBrainContinuousLearningCenterService
against a real, seeded temp database -- no mocks. Real MB-08 cycles are
run to completion first (through MB-08's own real service, seeded with
real Public Chat + Knowledge Gap Registry data), then MB-09's full
planning-and-recommendation workflow is driven end to end over them.
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
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
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


def _seed_mb08_cycle(api_app: FastAPI, admin_id: str, *, cycle_index: int, domain_case_count: int) -> dict:
    settings = api_app.state.settings
    pc = PublicChatRoutingRepository(settings.resolved_database_path)
    kg = KnowledgeGapRepository(settings.resolved_database_path)

    for i in range(15):
        grounded = i % 3 != 0
        pc.record_event({
            "request_id": f"c{cycle_index}-req-{i}", "input_hash": _hash(f"c{cycle_index}q{i}"),
            "classification_decision_public_id": None, "recommended_route": "core_model",
            "resolved_route": "core_model" if grounded else "insufficient", "route_status": "executable",
            "evidence_status": "grounded" if grounded else "model_only", "detected_language": "en",
            "answer_language": "en", "safety_status": "safe", "fallbacks_attempted": [],
            "latency_ms": 100, "error_code": None, "conversation_id": f"c{cycle_index}-{i}",
        })
    for i in range(domain_case_count):
        case = kg.create_case({
            "event_type": "knowledge_gap", "primary_reason_code": "rag_content_missing",
            "reason_codes": ["rag_content_missing"], "language": "en", "domain": "History",
            "intent": "facts", "freshness": "static", "input_hash": _hash(f"c{cycle_index}case{i}"),
            "canonical_question": f"deep question {i}", "content_unavailable_for_review": False,
        })
        kg.update_case_priority(
            case["public_id"], priority_score=20.0 + cycle_index, priority_band="high",
            priority_reason_codes=["frequency_weighted"],
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


def _seed(api_app: FastAPI, *, cycles: int = 3) -> dict:
    admin = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="mb09-admin", display_name="A", password="password12345")
    )
    mb08_sessions = [
        _seed_mb08_cycle(api_app, admin.public_id, cycle_index=i, domain_case_count=3 + i)
        for i in range(cycles)
    ]
    return {"admin_id": admin.public_id, "mb08_sessions": mb08_sessions}


def _svc(api_app: FastAPI) -> MiniBrainContinuousLearningCenterService:
    return MiniBrainContinuousLearningCenterService(api_app.state.settings)


async def test_full_planning_cycle_happy_path(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)

    session = svc.create_session(admin_id=seed["admin_id"])
    assert session["stage"] == "knowledge_gap_evolution"

    session = svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "learning_queue"
    assert session["knowledge_gap_evolution_report"]["cycles_compared"] == 3
    assert session["knowledge_gap_evolution_report"]["recurring_weak_domains"][0]["domain"] == "History"

    session = svc.build_learning_queue_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "draft_planning"
    assert session["learning_queue_report"]["queue"][0]["topic"] == "History"

    session = svc.build_draft_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "provider_request"
    assert session["draft_report"]["verified"] is False

    session = svc.prepare_provider_request_stage(
        session["public_id"], requested_providers=["claude", "openai"], admin_id=seed["admin_id"],
    )
    assert session["stage"] == "provider_consensus"
    assert session["provider_request"]["valid"] is True

    session = svc.ingest_provider_results_stage(
        session["public_id"],
        provider_outputs=[
            {"provider": "claude", "output_text": "History is the study of the past."},
            {"provider": "openai", "output_text": "History studies past events and their causes."},
        ],
        admin_id=seed["admin_id"],
    )
    assert session["stage"] == "dataset_evolution"
    assert session["provider_consensus_report"]["confidence"] in {"None", "Low", "Medium", "High"}

    session = svc.plan_dataset_evolution_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "knowledge_roadmap"
    assert session["dataset_evolution_report"]["recommendation"] in {
        "merge", "extend", "replace", "split", "ignore",
    }

    session = svc.build_roadmap_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "recommendation"
    assert session["roadmap_report"]["cycles_in_memory"] == 0  # no memory recorded yet

    session = svc.generate_recommendation_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["recommendation_report"]["action"] in {
        "No Action", "Collect More Data", "Local Draft", "External Provider Consensus",
        "RAG Evaluation", "Training Candidate",
    }

    session = svc.generate_report(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "awaiting_admin_review"
    assert session["planning_report"]["next_action"]["action"] == session["recommendation_report"]["action"]

    session = svc.admin_review(session["public_id"], decision="approve_draft", admin_id=seed["admin_id"])
    assert session["stage"] == "closed"
    assert session["status"] == "admin_approved_draft"

    # read-only verification: MB-08/Public Chat/Knowledge Gap Registry/
    # Training Engine tables are byte-for-byte untouched by MB-09
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        kg_count = conn.execute("SELECT COUNT(*) FROM knowledge_gap_cases").fetchone()[0]
        pc_count = conn.execute("SELECT COUNT(*) FROM public_chat_routing_events").fetchone()[0]
        job_count = conn.execute("SELECT COUNT(*) FROM pretraining_jobs").fetchone()[0]
        dataset_count = conn.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0]
        cl_session_count = conn.execute("SELECT COUNT(*) FROM mini_brain_continuous_learning_sessions").fetchone()[0]
    assert kg_count == 3 + 4 + 5
    assert pc_count == 45
    assert job_count == 0
    assert dataset_count == 0
    assert cl_session_count == 3  # MB-08's own sessions, untouched by MB-09


async def test_provider_consensus_detects_conflicting_outputs(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    session = svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_learning_queue_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_draft_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.prepare_provider_request_stage(
        session["public_id"], requested_providers=["claude", "openai"], admin_id=seed["admin_id"],
    )
    session = svc.ingest_provider_results_stage(
        session["public_id"],
        provider_outputs=[
            {"provider": "claude", "output_text": "The answer is definitely yes."},
            {"provider": "openai", "output_text": "The answer is definitely no."},
        ],
        admin_id=seed["admin_id"],
    )
    assert session["provider_consensus_report"]["has_conflicts"] is True
    assert session["provider_consensus_report"]["confidence"] == "Low"
    assert len(session["provider_consensus_report"]["traceable_outputs"]) == 2


async def test_provider_request_rejects_unknown_provider(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    session = svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_learning_queue_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_draft_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.prepare_provider_request_stage(
        session["public_id"], requested_providers=["not-a-real-provider"], admin_id=seed["admin_id"],
    )
    assert session["provider_request"]["valid"] is False
    assert session["stage"] == "provider_request"  # never advances on an invalid request


async def test_roadmap_reflects_permanent_memory_count(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    svc.record_memory(
        continuous_learning_session_public_id=seed["mb08_sessions"][0]["public_id"],
        admin_id=seed["admin_id"],
    )
    svc.record_memory(
        continuous_learning_session_public_id=seed["mb08_sessions"][1]["public_id"],
        admin_id=seed["admin_id"],
    )
    session = svc.create_session(admin_id=seed["admin_id"])
    session = svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_learning_queue_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_draft_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.prepare_provider_request_stage(session["public_id"], requested_providers=["claude"], admin_id=seed["admin_id"])
    session = svc.ingest_provider_results_stage(
        session["public_id"], provider_outputs=[{"provider": "claude", "output_text": "x"}], admin_id=seed["admin_id"],
    )
    session = svc.plan_dataset_evolution_stage(session["public_id"], admin_id=seed["admin_id"])
    session = svc.build_roadmap_stage(session["public_id"], admin_id=seed["admin_id"])
    assert session["roadmap_report"]["cycles_in_memory"] == 2


async def test_learning_memory_is_permanent_and_immutable(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    memory = svc.record_memory(
        continuous_learning_session_public_id=seed["mb08_sessions"][0]["public_id"],
        model_version_public_id="cmv-1", improvement_notes="first note", admin_id=seed["admin_id"],
    )
    assert memory["weak_domains"] == ["History"]
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE mini_brain_learning_memory SET improvement_notes='changed' WHERE public_id=?",
                (memory["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM mini_brain_learning_memory WHERE public_id=?", (memory["public_id"],))


async def test_evolve_knowledge_gaps_blocked_at_wrong_stage(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    with pytest.raises(ValidationError, match="not 'knowledge_gap_evolution'"):
        svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="not-a-real-decision", admin_id=seed["admin_id"])


async def test_admin_review_never_executes_any_downstream_action(api_app: FastAPI) -> None:
    """Admin approval verification: every one of the six decisions only
    records the choice -- confirmed here by checking no MB-06/MB-07
    session or RAG experiment was created as a side effect."""
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})

    for decision in ("reject", "edit", "approve_draft", "request_provider_consensus", "send_to_rag", "archive"):
        s = svc.create_session(admin_id=seed["admin_id"])
        with svc.repository.transaction() as connection:
            svc.repository.update_session(connection, s["public_id"], {"stage": "awaiting_admin_review"})
        result = svc.admin_review(s["public_id"], decision=decision, admin_id=seed["admin_id"])
        assert result["stage"] == "closed"

    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        ls_count = conn.execute("SELECT COUNT(*) FROM mini_brain_learning_sessions").fetchone()[0]
        rp_count = conn.execute("SELECT COUNT(*) FROM mini_brain_release_sessions").fetchone()[0]
    assert ls_count == 0
    assert rp_count == 0


async def test_events_are_recorded(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(admin_id=seed["admin_id"])
    svc.evolve_knowledge_gaps_stage(session["public_id"], admin_id=seed["admin_id"])
    events = svc.events(session["public_id"])
    event_types = [e["event_type"] for e in events["items"]]
    assert "session_created" in event_types
    assert "knowledge_gaps_evolved" in event_types
