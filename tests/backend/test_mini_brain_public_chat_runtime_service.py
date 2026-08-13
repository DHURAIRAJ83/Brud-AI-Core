"""MB-23: service-level tests for MiniBrainPublicChatRuntimeService
against a real, seeded temp database -- no mocks. A real public_chat-
scope model assignment and active memory policy are built through the
same real Admin API helpers `test_public_chat_routing_service.py`
already uses (genuine generation, nothing mocked), then MB-23's own
session/message/feedback/gap-detection/clustering/candidate/review
workflow is driven end to end over real `PublicChatRoutingService`
responses.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_public_chat_runtime_service import MiniBrainPublicChatRuntimeService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_public_chat_routing_service import (
    _build_public_chat_assignment,
    _create_active_memory_policy,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_web_search_process_state():
    from backend.services.web_search_cache import reset_cache
    from backend.services.web_search_provider import reset_provider_circuit

    reset_cache()
    reset_provider_circuit("wikipedia")
    yield


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports", document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports", core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts", release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True, log_level="CRITICAL", public_chat_model_enabled=True,
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _seed_public_chat_capability(app: FastAPI, *, slug: str) -> None:
    client, headers = await authenticated_client(app)
    try:
        await _build_public_chat_assignment(client, headers, app, slug=slug)
        await _create_active_memory_policy(client, headers)
    finally:
        await client.aclose()


def _svc(app: FastAPI) -> MiniBrainPublicChatRuntimeService:
    return MiniBrainPublicChatRuntimeService(app.state.settings)


# -- full workflow -----------------------------------------------------------------------------


async def test_full_workflow_session_to_candidate_review(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc1")
    svc = _svc(api_app)

    session = svc.start_session(raw_client_key="198.51.100.1", language="en")
    assert session["status"] == "active"

    result = svc.send_message(session["public_id"], raw_message="What is a noun in Tamil grammar?")
    assert "reply" in result
    result2 = svc.send_message(session["public_id"], raw_message="That is wrong, that did not answer my question")
    assert result2["signals_raised"] >= 1

    messages = svc.messages(session["public_id"])["items"]
    assert len(messages) == 4
    for message in messages:
        assert "content" not in message

    signals = svc.signals(session["public_id"])["items"]
    assert any(s["signal_type"] == "explicit_negative" for s in signals)

    close_result = svc.end_session(session["public_id"])
    assert close_result["session"]["status"] == "ended"
    assert close_result["report"]["no_automatic_training_occurred"] is True

    # second session, same topic -- so the cluster crosses the default threshold
    session_b = svc.start_session(raw_client_key="198.51.100.2", language="en")
    svc.send_message(session_b["public_id"], raw_message="What is a noun in Tamil grammar?")
    svc.send_message(session_b["public_id"], raw_message="That is wrong, that did not answer my question")
    svc.end_session(session_b["public_id"])

    generated = svc.run_generate_candidates(admin_id="admin-1", minimum_frequency=2)
    assert len(generated["items"]) >= 1
    candidate = generated["items"][0]
    assert candidate["status"] == "pending_admin_review"

    reviewed = svc.review_candidate(candidate["public_id"], admin_id="admin-1", decision="approve", notes="ok")
    assert reviewed["status"] == "approved"
    assert reviewed["reviewed_by_admin_public_id"] == "admin-1"


# -- guards -----------------------------------------------------------------------------------


async def test_send_message_requires_active_session(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc2")
    svc = _svc(api_app)
    session = svc.start_session(raw_client_key="198.51.100.3")
    svc.end_session(session["public_id"])
    with pytest.raises(ValidationError):
        svc.send_message(session["public_id"], raw_message="hello again")


async def test_end_session_twice_fails(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc3")
    svc = _svc(api_app)
    session = svc.start_session(raw_client_key="198.51.100.4")
    svc.end_session(session["public_id"])
    with pytest.raises(ValidationError):
        svc.end_session(session["public_id"])


async def test_submit_feedback_rejects_out_of_range_rating(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc4")
    svc = _svc(api_app)
    session = svc.start_session(raw_client_key="198.51.100.5")
    with pytest.raises(ValidationError):
        svc.submit_feedback(session["public_id"], satisfaction_rating=1.5, raw_comment=None)


async def test_submit_feedback_sanitizes_comment_before_storage(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc5")
    svc = _svc(api_app)
    session = svc.start_session(raw_client_key="198.51.100.6")
    svc.submit_feedback(
        session["public_id"], satisfaction_rating=0.1, raw_comment="email me at leak@example.com please",
    )
    signals = svc.signals(session["public_id"])["items"]
    assert signals
    for signal in signals:
        assert "leak@example.com" not in signal["normalized_text"]


async def test_review_candidate_rejects_unknown_decision(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc6")
    svc = _svc(api_app)
    session = svc.start_session(raw_client_key="198.51.100.7")
    svc.send_message(session["public_id"], raw_message="What is a noun in Tamil grammar?")
    svc.send_message(session["public_id"], raw_message="That is wrong")
    svc.end_session(session["public_id"])
    session_b = svc.start_session(raw_client_key="198.51.100.8")
    svc.send_message(session_b["public_id"], raw_message="What is a noun in Tamil grammar?")
    svc.send_message(session_b["public_id"], raw_message="That is wrong")
    svc.end_session(session_b["public_id"])

    generated = svc.run_generate_candidates(admin_id="admin-1", minimum_frequency=2)
    candidate = generated["items"][0]
    with pytest.raises(ValidationError):
        svc.review_candidate(candidate["public_id"], admin_id="admin-1", decision="maybe")


async def test_review_candidate_twice_fails(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc7")
    svc = _svc(api_app)
    for key in ("198.51.100.9", "198.51.100.10"):
        session = svc.start_session(raw_client_key=key)
        svc.send_message(session["public_id"], raw_message="What is a noun in Tamil grammar?")
        svc.send_message(session["public_id"], raw_message="That is wrong")
        svc.end_session(session["public_id"])

    generated = svc.run_generate_candidates(admin_id="admin-1", minimum_frequency=2)
    candidate = generated["items"][0]
    svc.review_candidate(candidate["public_id"], admin_id="admin-1", decision="approve")
    with pytest.raises(ValidationError):
        svc.review_candidate(candidate["public_id"], admin_id="admin-1", decision="reject")


async def test_regenerating_candidates_never_overwrites_a_reviewed_decision(api_app: FastAPI) -> None:
    await _seed_public_chat_capability(api_app, slug="svc8")
    svc = _svc(api_app)
    for key in ("198.51.100.11", "198.51.100.12"):
        session = svc.start_session(raw_client_key=key)
        svc.send_message(session["public_id"], raw_message="What is a noun in Tamil grammar?")
        svc.send_message(session["public_id"], raw_message="That is wrong")
        svc.end_session(session["public_id"])

    generated = svc.run_generate_candidates(admin_id="admin-1", minimum_frequency=2)
    candidate = generated["items"][0]
    svc.review_candidate(candidate["public_id"], admin_id="admin-1", decision="reject", notes="not a real gap")

    svc.run_generate_candidates(admin_id="admin-1", minimum_frequency=2)
    still = svc.candidate(candidate["public_id"])
    assert still["status"] == "rejected"


async def test_diagnostics_discloses_no_automatic_training(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    diagnostics = svc.diagnostics()
    assert diagnostics["mb22_training_started_or_finalized"] is False
    assert diagnostics["automatic_training_performed"] is False
    assert diagnostics["candidates_require_admin_review"] is True
