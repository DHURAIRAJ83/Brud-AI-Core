"""Phase 18 Step 29/31/32 -- Admin diagnostics API for the public
Smart Answer Router, the 5 read-only Admin Assistant tools, and the
public `/api/chat/help` deterministic FAQ endpoint."""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from backend.main import create_app
from backend.services.admin_assistant_tools import get_tool, run_tool
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _seed_event(settings: Settings, **overrides) -> dict:
    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    values = {
        "request_id": "req-1",
        "input_hash": "a" * 64,
        "recommended_route": "core_model",
        "resolved_route": "core_model",
        "route_status": "executable",
        "evidence_status": "model_only",
        "detected_language": "ta",
        "answer_language": "ta",
        "safety_status": "safe",
        "fallbacks_attempted": [],
    }
    values.update(overrides)
    return repo.record_event(values)


async def test_diagnostics_endpoints_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/public-chat-routing/overview")
        assert response.status_code == 401
        response = await client.get("/api/admin/public-chat-routing/events")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_overview_reports_real_counts_never_fabricated(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    _seed_event(settings, resolved_route="core_model")
    _seed_event(settings, request_id="req-2", resolved_route="clarify")
    _seed_event(
        settings, request_id="req-3", resolved_route="refuse", safety_status="refused"
    )

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/public-chat-routing/overview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_requests"] == 3
        assert body["by_resolved_route"]["core_model"] == 1
        assert body["clarification_count"] == 1
        assert body["refusal_count"] == 1
        assert body["insufficient_count"] == 0
        assert "language_compliance" in body
    finally:
        await client.aclose()


async def test_list_and_get_event_never_expose_raw_text(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    event = _seed_event(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/public-chat-routing/events", headers=headers)
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) == 1
        assert "message" not in events[0]
        assert "reply" not in events[0]
        assert events[0]["input_hash"] == "a" * 64

        response = await client.get(
            f"/api/admin/public-chat-routing/events/{event['public_id']}", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["public_id"] == event["public_id"]

        response = await client.get(
            "/api/admin/public-chat-routing/events/does-not-exist", headers=headers
        )
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_chat_help_endpoint_is_public_and_has_ten_bilingual_entries(
    api_app: FastAPI,
) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/chat/help")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 10
        assert len(body["entries"]) == 10
        for entry in body["entries"]:
            assert entry["question_en"]
            assert entry["question_ta"]
            assert entry["answer_en"]
            assert entry["answer_ta"]
    finally:
        await client.aclose()


def test_all_five_admin_assistant_tools_are_registered() -> None:
    for name in (
        "get_public_chat_routing_overview",
        "get_public_chat_route_event",
        "get_public_chat_language_compliance",
        "get_public_chat_safety_summary",
        "get_public_chat_unavailable_route_summary",
    ):
        assert get_tool(name) is not None


def test_public_chat_routing_overview_tool_returns_real_data(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "tools.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    _seed_event(settings)

    result = run_tool("get_public_chat_routing_overview", settings)
    assert result["available"] is True
    assert result["total_requests"] == 1

    result = run_tool("get_public_chat_safety_summary", settings)
    assert result["available"] is True
    assert result["total_requests"] == 1

    result = run_tool("get_public_chat_unavailable_route_summary", settings)
    assert result["available"] is True
    assert result["trusted_web_unavailable_count"] == 0

    result = run_tool("get_public_chat_language_compliance", settings)
    assert result["available"] is True
    assert result["language_policy_violations"] == 0


def test_public_chat_route_event_tool_reports_unavailable_for_unknown_id(
    tmp_path: Path,
) -> None:
    settings = Settings(
        database_path=tmp_path / "tools2.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)

    result = run_tool(
        "get_public_chat_route_event", settings, {"public_id": "does-not-exist"}
    )
    assert result["available"] is False
