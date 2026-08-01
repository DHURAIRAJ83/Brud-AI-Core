import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.anyio


async def api_request(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


async def test_health_endpoint(api_app: FastAPI) -> None:
    response = await api_request(api_app, "GET", "/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "brud-ai-backend",
        "version": "0.1.0",
        "database": "connected",
        "core_model": "not_configured",
    }


async def test_version_endpoint(api_app: FastAPI) -> None:
    response = await api_request(api_app, "GET", "/api/version")
    assert response.status_code == 200
    assert response.json() == {"project": "Brud AI", "version": "0.1.0", "phase": 9}


async def test_chat_endpoint_returns_real_routing_response(api_app: FastAPI) -> None:
    """Phase 18: /api/chat is a real public Smart Answer Router, not the
    Phase 1 placeholder -- no model/route is available in a fresh
    database, so this honestly resolves to `insufficient`, never a
    fabricated "foundation is working" placeholder reply."""

    response = await api_request(api_app, "POST", "/api/chat", json={"message": "வணக்கம்"})
    assert response.status_code == 200
    body = response.json()
    assert body["route_used"] in (
        "core_model", "approved_rag", "memory", "clarify", "refuse", "insufficient",
    )
    assert "model" not in body
    assert "phase" not in body
    assert body["reply"]
    assert body["request_id"]


async def test_chat_validates_empty_messages(api_app: FastAPI) -> None:
    response = await api_request(api_app, "POST", "/api/chat", json={"message": ""})
    assert response.status_code == 422


async def test_chat_rejects_tanglish_output_override(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "hi", "language_override": "tanglish"}
    )
    assert response.status_code == 422


async def test_chat_capabilities_endpoint(api_app: FastAPI) -> None:
    response = await api_request(api_app, "GET", "/api/chat/capabilities")
    assert response.status_code == 200
    body = response.json()
    # Phase 20: the built-in Wikipedia provider needs no API key, so
    # trusted_web_available is genuinely True out of the box (its
    # health_check() only inspects in-process circuit-breaker state, no
    # real network call) -- same reasoning for the three built-in
    # deterministic tools, which also need no external credential.
    assert body["trusted_web_available"] is True
    assert body["tool_available"] is True
    assert body["calculator_available"] is True
    assert body["unit_conversion_available"] is True
    assert body["date_time_arithmetic_available"] is True
    assert body["external_mcp_enabled"] is False


async def test_admin_overview_endpoint(protected_api_app: FastAPI) -> None:
    response = await api_request(protected_api_app, "GET", "/api/admin/overview")
    assert response.status_code == 200
    assert response.json() == {
        "project": "Brud AI",
        "phase": 9,
        "chatbot_status": "foundation_ready",
        "admin_dashboard_status": "foundation_ready",
        "core_model_status": "not_trained",
        "dataset_records": 0,
        "dataset_sources": 0,
        "ready_dataset_versions": 0,
        "training_jobs": 0,
        "completed_training_jobs": 0,
        "registered_tokenizer_versions": 0,
        "registered_models": 0,
    }
