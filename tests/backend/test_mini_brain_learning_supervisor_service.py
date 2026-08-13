"""MB-06: service-level tests for MiniBrainLearningSupervisorService
against a real, seeded temp database -- no mocks. Central concerns:
every stage-order/decision gate is enforced, a submitted training job
is real but never executed by this service, and every table this
service is not supposed to touch is left byte-for-byte unchanged.
"""

import sqlite3

import pytest
from fastapi import FastAPI

from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
)
from tests.backend.test_pretraining_api import _fixture_refs

pytestmark = pytest.mark.anyio

QUESTIONS = ["What is Python used for?", "How does TCP networking work?", "Explain machine learning basics"]


def _create_admin(app: FastAPI, username: str = "ls-admin") -> str:
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="A", password="password12345")
    )
    return admin.public_id


def _seed_dataset(app: FastAPI, admin_id: str, count: int = 60) -> str:
    dataset_service = DatasetService(DatasetAdminRepository(app.state.settings.resolved_database_path))
    source = dataset_service.create_source(
        ManualSourceCreate(name="LS Set", language="en", source_type="manual"), admin_id,
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


def _dataset_snapshot(app: FastAPI) -> tuple:
    with sqlite3.connect(app.state.settings.resolved_database_path) as conn:
        conn.row_factory = sqlite3.Row
        sources = [dict(r) for r in conn.execute("SELECT * FROM dataset_sources ORDER BY id")]
        records = [dict(r) for r in conn.execute("SELECT * FROM dataset_records ORDER BY id")]
    return sources, records


def _table_count(app: FastAPI, table: str) -> int:
    with sqlite3.connect(app.state.settings.resolved_database_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# -- stage progression + decision gates ----------------------------------------


async def test_dataset_validation_and_approve_advances_to_rag_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    before_sources, before_records = _dataset_snapshot(api_app)

    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    assert session["stage"] == "dataset_validation"
    assert session["status"] == "in_progress"

    session = svc.validate_dataset(session["public_id"], admin_id=admin_id)
    assert session["stage"] == "awaiting_dataset_decision"
    readiness = session["dataset_readiness_report"]["training_readiness"]
    assert readiness["status"] in {"Ready", "Needs Improvement", "Not Ready"}
    assert "advanced_report" in session["dataset_readiness_report"]

    session = svc.decide_dataset(session["public_id"], decision="approve", admin_id=admin_id)
    assert session["stage"] == "rag_evaluation"
    assert session["dataset_decision"] == "approve"
    assert session["dataset_decided_by"] == admin_id

    after_sources, after_records = _dataset_snapshot(api_app)
    assert after_sources == before_sources
    assert after_records == before_records


async def test_dataset_validation_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)

    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    session = svc.validate_dataset(session["public_id"], admin_id=admin_id)
    session = svc.decide_dataset(session["public_id"], decision="reject", admin_id=admin_id)

    assert session["stage"] == "closed"
    assert session["status"] == "rejected_at_dataset"


async def test_decide_dataset_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    svc.validate_dataset(session["public_id"], admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.decide_dataset(session["public_id"], decision="maybe", admin_id=admin_id)


async def test_decide_dataset_blocked_before_validation(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.decide_dataset(session["public_id"], decision="approve", admin_id=admin_id)


async def test_submit_training_request_blocked_at_wrong_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.submit_training_request(
            session["public_id"], name="x", dataset_version_public_id="dv",
            tokenizer_version_public_id="tv", core_model_version_public_id="cv", admin_id=admin_id,
        )


async def test_submit_training_request_blocked_without_rag_approval(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    svc.validate_dataset(session["public_id"], admin_id=admin_id)
    session = svc.decide_dataset(session["public_id"], decision="approve", admin_id=admin_id)

    # fast-forward past the RAG gate without ever approving it (repository-level,
    # simulating an admin who tries to skip the gate by calling stage 7 directly)
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "training_request"})

    before_job_count = _table_count(api_app, "pretraining_jobs")
    with pytest.raises(ValidationError, match="RAG evaluation has not been approved"):
        svc.submit_training_request(
            session["public_id"], name="x", dataset_version_public_id="dv",
            tokenizer_version_public_id="tv", core_model_version_public_id="cv", admin_id=admin_id,
        )
    assert _table_count(api_app, "pretraining_jobs") == before_job_count


# -- real training request submission (no execution) ----------------------------


async def test_submit_training_request_creates_real_draft_job_and_never_executes_it(
    api_app: FastAPI,
) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    refs = _fixture_refs(api_app)

    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    session = svc.validate_dataset(session["public_id"], admin_id=admin_id)
    session = svc.decide_dataset(session["public_id"], decision="approve", admin_id=admin_id)

    # drive straight through the RAG gate as "approved" -- the RAG Sandbox lifecycle
    # itself is covered by its own existing test suite, not re-tested here
    with svc.repository.transaction() as connection:
        svc.repository.update_session(
            connection, session["public_id"], {"stage": "training_request", "rag_decision": "approve"},
        )

    before_job_count = _table_count(api_app, "pretraining_jobs")
    session = svc.submit_training_request(
        session["public_id"], name="mb06-test-job",
        dataset_version_public_id=refs["dataset"], tokenizer_version_public_id=refs["tokenizer"],
        core_model_version_public_id=refs["model"], admin_id=admin_id,
    )

    assert session["stage"] == "training_monitoring"
    assert session["status"] == "training_requested"
    job_public_id = session["training_job_public_id"]
    assert job_public_id

    assert _table_count(api_app, "pretraining_jobs") == before_job_count + 1
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        conn.row_factory = sqlite3.Row
        job_row = conn.execute(
            "SELECT status FROM pretraining_jobs WHERE public_id=?", (job_public_id,)
        ).fetchone()
    # "draft" (not queued, not running) proves MB-06 only submitted the job --
    # it never called validate_job/queue_job/run_one on it.
    assert job_row["status"] == "draft"

    monitor = svc.monitor_training(session["public_id"])
    assert monitor["job"]["public_id"] == job_public_id
    assert monitor["job"]["status"] == "draft"

    with pytest.raises(ValidationError, match="still running"):
        svc.analyze_training_result(session["public_id"], admin_id=admin_id)


async def test_monitor_training_blocked_without_a_submitted_job(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.monitor_training(session["public_id"])


# -- admin review + release candidate gating -------------------------------------


async def test_admin_review_reject_closes_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})

    session = svc.admin_review(session["public_id"], decision="reject", admin_id=admin_id)
    assert session["stage"] == "closed"
    assert session["status"] == "admin_rejected"


async def test_admin_review_accept_moves_to_release_candidate_stage(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})

    session = svc.admin_review(session["public_id"], decision="accept", admin_id=admin_id)
    assert session["stage"] == "release_candidate"
    assert session["admin_final_decision"] == "accept"
    # accept does not itself create the release candidate -- no core model
    # version was written just by recording the decision
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM core_model_versions").fetchone()[0]
    assert count == 0


async def test_release_candidate_blocked_without_accept_decision(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)

    with pytest.raises(ValidationError):
        svc.create_release_candidate(session["public_id"], checkpoint_public_id="cp1", admin_id=admin_id)


async def test_admin_review_rejects_invalid_decision_value(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})

    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="approve", admin_id=admin_id)


# -- own-state persistence ---------------------------------------------------------


async def test_events_are_recorded_append_only_and_readable(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)
    svc.validate_dataset(session["public_id"], admin_id=admin_id)
    svc.decide_dataset(session["public_id"], decision="approve", admin_id=admin_id)

    events = svc.events(session["public_id"])
    event_types = [e["event_type"] for e in events["items"]]
    assert "session_created" in event_types
    assert "dataset_validated" in event_types
    assert "dataset_approved" in event_types


async def test_list_sessions_returns_created_session(api_app: FastAPI) -> None:
    admin_id = _create_admin(api_app)
    source_id = _seed_dataset(api_app, admin_id)
    svc = MiniBrainLearningSupervisorService(api_app.state.settings)
    session = svc.create_session(dataset_source_public_id=source_id, admin_id=admin_id)

    sessions = svc.list_sessions()
    assert any(s["public_id"] == session["public_id"] for s in sessions["items"])
