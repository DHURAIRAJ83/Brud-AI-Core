"""MB-12: service-level tests for MiniBrainPipelineCoordinatorService
against a real, seeded temp database -- no mocks. Real MB-09, MB-10,
and MB-06 sessions (and a real MB-11 session run to completion) are
built first, then MB-12's linking chain is driven end to end over them.
"""

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
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from backend.services.mini_brain_dataset_evolution_service import MiniBrainDatasetEvolutionService
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
)
from backend.services.mini_brain_pipeline_coordinator_service import (
    MiniBrainPipelineCoordinatorService,
)
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


def _create_admin(app: FastAPI, username: str = "pc-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainPipelineCoordinatorService:
    return MiniBrainPipelineCoordinatorService(app.state.settings)


def _seed_dataset_source(app: FastAPI, admin_id: str, count: int = 40) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="PC Set", language="en", source_type="manual"), admin_id,
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


def _seed_mb09_session(app: FastAPI, admin_id: str) -> dict:
    return MiniBrainContinuousLearningCenterService(app.state.settings).create_session(admin_id=admin_id)


def _seed_mb10_local_draft_session(app: FastAPI, admin_id: str, topic: str) -> dict:
    svc = MiniBrainResearchCenterService(app.state.settings)
    session = svc.create_session(topic=topic, admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    session = svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    return session


def _seed_mb10_provider_consensus_pending_session(app: FastAPI, admin_id: str, topic: str) -> dict:
    svc = MiniBrainResearchCenterService(app.state.settings)
    session = svc.create_session(topic=topic, admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(
        session["public_id"], mode="multi_provider", requested_provider_keys=["claude"], admin_id=admin_id,
    )
    session = svc.prepare_provider_request_package_stage(session["public_id"], admin_id=admin_id)
    provider_outputs = [{"provider": "claude", "output_text": "According to sources (2020), quantum computing uses qubits."}]
    session = svc.ingest_provider_results_stage(session["public_id"], provider_outputs=provider_outputs, admin_id=admin_id)
    return session


def _seed_mb11_session(app: FastAPI, admin_id: str, dataset_source_public_id: str) -> dict:
    svc = MiniBrainDatasetEvolutionService(app.state.settings)
    session = svc.create_session(dataset_source_public_id=dataset_source_public_id, admin_id=admin_id)
    session = svc.run_knowledge_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_dataset_evolution_stage(session["public_id"], admin_id=admin_id)
    session = svc.run_evolution_simulation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_recommendation_stage(session["public_id"], admin_id=admin_id)
    session = svc.generate_report(session["public_id"], admin_id=admin_id)
    return session


def _seed_mb06_session(app: FastAPI, admin_id: str, dataset_source_public_id: str) -> dict:
    svc = MiniBrainLearningSupervisorService(app.state.settings)
    return svc.create_session(dataset_source_public_id=dataset_source_public_id, admin_id=admin_id)


def _inject_passing_rag_report_into_mb11_session(app: FastAPI, mb11_session_public_id: str) -> None:
    """A real RAG Sandbox generation/evaluation run needs a full
    corpus/index/retrieval-run fixture that MB-11's own test suite does
    not build either (see its own service tests) -- this follows that
    same established precedent: inject a synthetic passing report
    directly, exactly the shape `check_rag_gate` expects."""
    report = {
        "production_rag_readiness": "potentially_ready",
        "citation_metrics": {"citation_validity_rate": 0.95},
        "threshold_evaluation": [{"dimension": "maximum_hallucination_rate", "passed": True}],
    }
    with sqlite3.connect(app.state.settings.resolved_database_path) as conn:
        conn.execute(
            "UPDATE mini_brain_dataset_evolution_sessions SET rag_report_json=?, rag_admin_decision=? WHERE public_id=?",
            (json.dumps(report), "approve", mb11_session_public_id),
        )
        conn.commit()


# -- full linking chain, real evidence throughout --------------------------------------------


async def test_full_linking_chain_with_real_evidence(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    mb09_session = _seed_mb09_session(api_app, admin_id)
    mb10_session = _seed_mb10_local_draft_session(api_app, admin_id, topic="Programming")
    mb11_session = _seed_mb11_session(api_app, admin_id, source_public_id)
    mb06_session = _seed_mb06_session(api_app, admin_id, source_public_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="Programming", admin_id=admin_id)
    assert session["stage"] == "new"

    session = svc.link_research_stage(session["public_id"], mb09_session_public_id=mb09_session["public_id"], admin_id=admin_id)
    assert session["stage"] == "under_research"
    assert session["mb09_session_public_id"] == mb09_session["public_id"]

    session = svc.link_research_center_stage(session["public_id"], mb10_session_public_id=mb10_session["public_id"], admin_id=admin_id)
    assert session["stage"] == "draft_ready"

    session = svc.link_dataset_evolution_stage(session["public_id"], mb11_session_public_id=mb11_session["public_id"], admin_id=admin_id)
    assert session["stage"] == "dataset_planned"

    session = svc.run_rag_first_enforcement(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "dataset_planned"
    assert session["rag_first_report"]["passed"] is False

    _inject_passing_rag_report_into_mb11_session(api_app, mb11_session["public_id"])
    session = svc.run_rag_first_enforcement(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "rag_testing"
    assert session["rag_first_report"]["passed"] is True

    session = svc.generate_training_readiness_report(session["public_id"], admin_id=admin_id)
    assert session["training_readiness_report"]["sources_available"] >= 3

    session = svc.generate_timeline(session["public_id"], admin_id=admin_id)
    assert session["lifecycle_timeline"]["event_count"] > 0

    session = svc.predict_improvement_stage(session["public_id"], admin_id=admin_id)
    assert "expected_benchmark_gain" in session["improvement_prediction"]

    session = svc.generate_recommendation(session["public_id"], admin_id=admin_id)
    assert session["recommendation_report"]["action"] in {
        "continue", "pause", "research_more", "request_providers", "improve_dataset", "retry_rag",
        "approve_training", "reject", "archive",
    }

    session = svc.generate_master_report(session["public_id"], admin_id=admin_id)
    assert session["master_report"]["ready_for_admin_review"] is True

    session = svc.link_training_stage(session["public_id"], mb06_session_public_id=mb06_session["public_id"], admin_id=admin_id)
    assert session["stage"] == "training_candidate"
    assert session["mb06_session_public_id"] == mb06_session["public_id"]


async def test_provider_consensus_pending_path_and_refresh(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mb09_session = _seed_mb09_session(api_app, admin_id)
    mb10_session = _seed_mb10_provider_consensus_pending_session(api_app, admin_id, topic="Quantum")

    svc = _svc(api_app)
    session = svc.create_session(topic="Quantum", admin_id=admin_id)
    session = svc.link_research_stage(session["public_id"], mb09_session_public_id=mb09_session["public_id"], admin_id=admin_id)

    session = svc.link_research_center_stage(session["public_id"], mb10_session_public_id=mb10_session["public_id"], admin_id=admin_id)
    assert session["stage"] == "provider_consensus_pending"

    session = svc.refresh_research_center_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "provider_consensus_pending"  # no draft yet -- unchanged

    research_center = MiniBrainResearchCenterService(api_app.state.settings)
    research_center.build_dataset_draft_stage(mb10_session["public_id"], admin_id=admin_id)

    session = svc.refresh_research_center_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "draft_ready"


async def test_link_research_center_rejects_session_without_draft_or_consensus(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mb09_session = _seed_mb09_session(api_app, admin_id)
    research_center = MiniBrainResearchCenterService(api_app.state.settings)
    mb10_session = research_center.create_session(topic="Empty", admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="Empty", admin_id=admin_id)
    session = svc.link_research_stage(session["public_id"], mb09_session_public_id=mb09_session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError, match="has not reached provider consensus"):
        svc.link_research_center_stage(session["public_id"], mb10_session_public_id=mb10_session["public_id"], admin_id=admin_id)


# -- stage-skip guard -----------------------------------------------------------------------


async def test_stage_skip_guard(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    mb11_session = _seed_mb11_session(api_app, admin_id, source_public_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="Skip Guard", admin_id=admin_id)

    with pytest.raises(ValidationError, match="stage transition blocked"):
        svc.link_dataset_evolution_stage(session["public_id"], mb11_session_public_id=mb11_session["public_id"], admin_id=admin_id)


async def test_recommendation_blocked_before_training_readiness(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="No Readiness Yet", admin_id=admin_id)

    with pytest.raises(ValidationError, match="generate the training readiness report"):
        svc.generate_recommendation(session["public_id"], admin_id=admin_id)


async def test_master_report_blocked_before_recommendation(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="No Recommendation Yet", admin_id=admin_id)
    svc.generate_training_readiness_report(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError, match="generate the recommendation"):
        svc.generate_master_report(session["public_id"], admin_id=admin_id)


# -- Admin Decision Center -------------------------------------------------------------------


async def test_admin_decide_all_nine_decisions(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)

    expected_status = {
        "continue": "in_progress", "pause": "admin_paused", "research_more": "admin_requested_more_research",
        "request_providers": "admin_requested_providers", "improve_dataset": "admin_requested_dataset_improvement",
        "retry_rag": "admin_retried_rag", "approve_training": "admin_approved_training",
        "reject": "admin_rejected", "archive": "admin_archived",
    }
    for decision, status in expected_status.items():
        session = svc.create_session(topic=f"Decision {decision}", admin_id=admin_id)
        session = svc.admin_decide(session["public_id"], decision=decision, admin_id=admin_id)
        assert session["status"] == status
        if decision == "archive":
            assert session["stage"] == "archived"


async def test_admin_decide_rejects_invalid_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Bad Decision", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_decide(session["public_id"], decision="bogus", admin_id=admin_id)


# -- events + listing --------------------------------------------------------------------------


async def test_events_are_recorded_append_only_and_readable(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    mb09_session = _seed_mb09_session(api_app, admin_id)
    svc = _svc(api_app)
    session = svc.create_session(topic="Events", admin_id=admin_id)
    svc.link_research_stage(session["public_id"], mb09_session_public_id=mb09_session["public_id"], admin_id=admin_id)
    events = svc.events(session["public_id"])["items"]
    assert len(events) == 2
    assert events[-1]["event_type"] == "session_created"


async def test_list_sessions_returns_created_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Listing", admin_id=admin_id)
    listed = svc.list_sessions()["items"]
    assert any(s["public_id"] == session["public_id"] for s in listed)
