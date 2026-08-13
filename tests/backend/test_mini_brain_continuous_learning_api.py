"""MB-08: API tests for /admin/mini-brain/continuous-learning.

Auth/CSRF requirements and route wiring over real HTTP. The full
10-stage real pipeline is already proven at the service layer in
test_mini_brain_continuous_learning_service.py -- this file confirms
the routes correctly translate HTTP requests into those same service
calls.
"""

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBCL = "/api/admin/mini-brain/continuous-learning"


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


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBCL}/sessions")).status_code == 401
        assert (await client.get(f"{MBCL}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_advisory_only_scope(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBCL}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["ai_model_used"] is False
        assert "own tables only" in body["writes_scope"]
        assert len(body["pipeline_stages"]) == 10
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBCL}/sessions", json={"cycle_window_days": 30})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_create_and_drive_session_over_http(api_app: FastAPI) -> None:
    pc = PublicChatRoutingRepository(api_app.state.settings.resolved_database_path)
    for i in range(5):
        pc.record_event({
            "request_id": f"req-{i}", "input_hash": _hash(f"q{i}"),
            "classification_decision_public_id": None, "recommended_route": "core_model",
            "resolved_route": "core_model", "route_status": "executable", "evidence_status": "grounded",
            "detected_language": "en", "answer_language": "en", "safety_status": "safe",
            "fallbacks_attempted": [], "latency_ms": 50, "error_code": None, "conversation_id": f"c{i}",
        })

    client, headers = await authenticated_client(api_app)
    try:
        create_response = await client.post(
            f"{MBCL}/sessions", headers=headers, json={"cycle_window_days": 14},
        )
        assert create_response.status_code == 200, create_response.text
        session = create_response.json()
        assert session["stage"] == "feedback_collection"
        session_id = session["public_id"]

        get_response = await client.get(f"{MBCL}/sessions/{session_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["public_id"] == session_id

        list_response = await client.get(f"{MBCL}/sessions", headers=headers)
        assert any(s["public_id"] == session_id for s in list_response.json()["items"])

        feedback_response = await client.post(f"{MBCL}/sessions/{session_id}/feedback", headers=headers)
        assert feedback_response.status_code == 200, feedback_response.text
        assert feedback_response.json()["stage"] == "failure_analysis"
        assert feedback_response.json()["feedback_report"]["total_conversations_observed"] == 5

        events_response = await client.get(f"{MBCL}/sessions/{session_id}/events", headers=headers)
        event_types = [e["event_type"] for e in events_response.json()["items"]]
        assert "feedback_collected" in event_types

        # wrong-stage guard surfaces as 422 at the HTTP layer too
        wrong_stage = await client.post(f"{MBCL}/sessions/{session_id}/feedback", headers=headers)
        assert wrong_stage.status_code == 422
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBCL}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()
