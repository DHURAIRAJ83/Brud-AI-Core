"""MB-10: service-level tests for MiniBrainResearchCenterService
against a real, seeded temp database -- no mocks. Covers both admin
workflow modes end to end, every stage-order guard, the RAG FIRST
POLICY's two-step accept/send gate, the real (read-only) MB-09 and
MB-06 integrations, and the permanent research memory.

The real RAG Sandbox generation/evaluation chain requires a full
corpus/index/retrieval-run fixture that MB-06's own service test suite
does not build either (see test_mini_brain_learning_supervisor_
service.py's direct-DB-manipulation bypass at its RAG stage) -- this
file follows that same established precedent: it proves the RAG FIRST
POLICY's admin gates and the stage machine around the RAG chain, and
bypasses the chain itself the same way MB-06's own tests do.
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
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
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


def _create_admin(app: FastAPI, username: str = "rc-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _svc(app: FastAPI) -> MiniBrainResearchCenterService:
    return MiniBrainResearchCenterService(app.state.settings)


def _seed_dataset_source(app: FastAPI, admin_id: str, count: int = 20) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="RC Set", language="en", source_type="manual"), admin_id,
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


def _bypass_to_awaiting_rag_review(app: FastAPI, session_public_id: str) -> None:
    with sqlite3.connect(app.state.settings.resolved_database_path) as conn:
        conn.execute(
            "UPDATE mini_brain_research_sessions SET stage=?, rag_report_json=? WHERE public_id=?",
            (
                "awaiting_rag_review",
                json.dumps({"production_rag_readiness": "ready_for_admin_review", "coverage": 0.9}),
                session_public_id,
            ),
        )
        conn.commit()


PROVIDER_OUTPUTS = [
    {"provider": "claude", "output_text": "According to physicists (2019), quantum computing uses qubits. Source: textbook."},
    {"provider": "openai", "output_text": "Quantum computing always definitely means only faster computers with no exceptions whatsoever certainly."},
]


# -- Mode 1: local draft ----------------------------------------------------------------


async def test_local_draft_full_happy_path_ends_with_archive(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)

    session = svc.create_session(topic="Photosynthesis", admin_id=admin_id)
    assert session["stage"] == "research_request"

    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "mode_selection"
    assert len(session["research_request"]["questions"]) == 3

    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    assert session["stage"] == "local_draft"
    assert session["selected_providers"] == []

    session = svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "dataset_draft"
    assert session["local_draft_report"]["status"] == "prepared"

    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "awaiting_draft_review"
    assert session["dataset_draft"]["verified"] is False
    assert session["recommendation_report"]["recommendation"] is None

    session = svc.admin_review_draft(session["public_id"], decision="archive", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_archived"


async def test_local_draft_can_read_existing_dataset_intelligence(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_public_id = _seed_dataset_source(api_app, admin_id)
    svc = _svc(api_app)

    session = svc.create_session(topic="Programming", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    session = svc.build_local_draft_stage(
        session["public_id"], existing_dataset_source_public_id=source_public_id, admin_id=admin_id,
    )
    context = session["local_draft_report"]["existing_dataset_context"]
    assert context["existing_dataset_source_public_id"] == source_public_id
    assert context["record_count"] == 20


# -- Mode 2: multi-provider consensus -----------------------------------------------------


async def test_multi_provider_full_happy_path_through_send_to_rag(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)

    session = svc.create_session(topic="Quantum Computing", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(
        session["public_id"], mode="multi_provider", requested_provider_keys=["claude", "openai"], admin_id=admin_id,
    )
    assert session["stage"] == "provider_request"
    assert {p["provider_key"] for p in session["selected_providers"]} == {"claude", "openai"}

    session = svc.prepare_provider_request_package_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "provider_consensus"
    assert set(session["provider_request"]["providers"]) == {"claude", "openai"}

    session = svc.ingest_provider_results_stage(
        session["public_id"], provider_outputs=PROVIDER_OUTPUTS, admin_id=admin_id,
    )
    assert session["stage"] == "dataset_draft"
    assert session["consensus_report"]["verdict"] == "conflicting"
    assert session["quality_report"]["overall_quality"] > 0

    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "awaiting_draft_review"
    assert session["dataset_draft"]["verified"] is False
    assert session["recommendation_report"]["recommendation"] in {
        "edit", "accept_draft", "request_more_research", "request_different_providers",
    }

    session = svc.admin_review_draft(session["public_id"], decision="accept_draft", admin_id=admin_id)
    assert session["status"] == "admin_accepted_draft"
    assert session["stage"] == "awaiting_draft_review"

    session = svc.admin_review_draft(session["public_id"], decision="send_to_rag", admin_id=admin_id)
    assert session["stage"] == "rag_evaluation"
    assert session["status"] == "admin_sent_to_rag"


async def test_send_to_rag_blocked_without_prior_accept(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Guard", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    session = svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError, match="must be accepted"):
        svc.admin_review_draft(session["public_id"], decision="send_to_rag", admin_id=admin_id)


async def test_select_mode_with_unknown_provider_key_stays_at_mode_selection(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Bad Providers", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(
        session["public_id"], mode="multi_provider", requested_provider_keys=["claude", "bogus"], admin_id=admin_id,
    )
    assert session["stage"] == "mode_selection"
    assert len(session["selected_providers"]) == 1


# -- stage-order guards --------------------------------------------------------------------


async def test_stage_order_guards_reject_out_of_order_calls(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Order Check", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.admin_review_draft(session["public_id"], decision="archive", admin_id=admin_id)


# -- MB-09 (read-only) integration ----------------------------------------------------------


async def test_research_request_folds_in_real_mb09_session_evidence(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    planning = MiniBrainContinuousLearningCenterService(api_app.state.settings)
    mb09_session = planning.create_session(admin_id=admin_id)

    svc = _svc(api_app)
    session = svc.create_session(topic="Evidence Check", admin_id=admin_id)
    session = svc.prepare_research_request_stage(
        session["public_id"], planning_center_session_public_id=mb09_session["public_id"], admin_id=admin_id,
    )
    evidence = session["research_request"]["evidence"]
    assert set(evidence) == {"knowledge_gap_evolution", "learning_queue", "roadmap", "recommendation"}


# -- provider registry ---------------------------------------------------------------------


async def test_provider_registry_seeded_with_five_defaults(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    providers = svc.list_providers()["items"]
    assert {p["provider_key"] for p in providers} == {"claude", "openai", "gemini", "openrouter", "local_model"}
    local_model = next(p for p in providers if p["provider_key"] == "local_model")
    assert local_model["requires_external_call"] is False


async def test_add_provider_and_toggle_status(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    provider = svc.add_provider(
        provider_key="mistral", display_name="Mistral", requires_external_call=True,
        description="Third-party -- admin-added, never hardcoded", admin_id=admin_id,
    )
    assert provider["provider_key"] == "mistral"
    assert provider["status"] == "active"

    with pytest.raises(ValidationError):
        svc.add_provider(
            provider_key="mistral", display_name="Mistral", requires_external_call=True,
            description="dup", admin_id=admin_id,
        )

    updated = svc.set_provider_status("mistral", status="inactive", admin_id=admin_id)
    assert updated["status"] == "inactive"


# -- learning memory (permanent, insert-only) -----------------------------------------------


async def test_record_memory_captures_session_history(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Memory Check", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    session = svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)

    entry = svc.record_memory(session["public_id"], notes="mid-cycle snapshot", admin_id=admin_id)
    assert entry["research_session_public_id"] == session["public_id"]
    assert entry["dataset_evolution"]["status"] == "needs_admin_review"
    assert entry["notes"] == "mid-cycle snapshot"

    listed = svc.list_memory()["items"]
    assert len(listed) == 1
    fetched = svc.get_memory(entry["public_id"])
    assert fetched["public_id"] == entry["public_id"]


# -- RAG review, training gate, and MB-06 (read-only) integration -------------------------------


async def test_rag_review_training_gate_and_training_report_analysis(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)

    session = svc.create_session(topic="Cell Biology", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(
        session["public_id"], mode="multi_provider", requested_provider_keys=["claude"], admin_id=admin_id,
    )
    session = svc.prepare_provider_request_package_stage(session["public_id"], admin_id=admin_id)
    session = svc.ingest_provider_results_stage(
        session["public_id"],
        provider_outputs=[{"provider": "claude", "output_text": (
            "According to biologists (2021), cells are the basic unit of life. Source: biology textbook, "
            "covering membranes, organelles, and cellular respiration in reasonable depth for a summary."
        )}],
        admin_id=admin_id,
    )
    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.admin_review_draft(session["public_id"], decision="accept_draft", admin_id=admin_id)
    session = svc.admin_review_draft(session["public_id"], decision="send_to_rag", admin_id=admin_id)
    assert session["stage"] == "rag_evaluation"

    _bypass_to_awaiting_rag_review(api_app, session["public_id"])

    session = svc.admin_review_rag(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "training_gate"
    assert session["status"] == "rag_admin_approved"

    session = svc.check_training_gate_stage(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "training_eligible"
    assert session["training_gate_report"]["eligible"] is True

    not_yet_eligible = svc.create_session(topic="Not Eligible Yet", admin_id=admin_id)
    with pytest.raises(ValidationError):
        svc.analyze_training_report(
            not_yet_eligible["public_id"], learning_supervisor_session_public_id="x", admin_id=admin_id,
        )

    dataset_source_public_id = _seed_dataset_source(api_app, admin_id)
    learning_supervisor = MiniBrainLearningSupervisorService(api_app.state.settings)
    mb06_session = learning_supervisor.create_session(
        dataset_source_public_id=dataset_source_public_id, admin_id=admin_id,
    )

    session = svc.analyze_training_report(
        session["public_id"], learning_supervisor_session_public_id=mb06_session["public_id"], admin_id=admin_id,
    )
    mb06_analysis = session["training_gate_report"]["mb06_analysis"]
    assert mb06_analysis["learning_supervisor_session_public_id"] == mb06_session["public_id"]
    assert mb06_analysis["training_report"] == mb06_session["training_report"]


async def test_rag_review_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Reject RAG", admin_id=admin_id)
    session = svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    session = svc.select_mode_stage(session["public_id"], mode="local_draft", admin_id=admin_id)
    session = svc.build_local_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.build_dataset_draft_stage(session["public_id"], admin_id=admin_id)
    session = svc.admin_review_draft(session["public_id"], decision="accept_draft", admin_id=admin_id)
    session = svc.admin_review_draft(session["public_id"], decision="send_to_rag", admin_id=admin_id)

    _bypass_to_awaiting_rag_review(api_app, session["public_id"])

    session = svc.admin_review_rag(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "rag_admin_rejected"


# -- events -----------------------------------------------------------------------------------


async def test_events_are_recorded_append_only_and_readable(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Events", admin_id=admin_id)
    svc.prepare_research_request_stage(session["public_id"], admin_id=admin_id)
    events = svc.events(session["public_id"])["items"]
    assert len(events) == 2
    assert events[-1]["event_type"] == "session_created"


async def test_list_sessions_returns_created_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    svc = _svc(api_app)
    session = svc.create_session(topic="Listing", admin_id=admin_id)
    listed = svc.list_sessions()["items"]
    assert any(s["public_id"] == session["public_id"] for s in listed)
