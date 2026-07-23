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


async def test_temporary_chat_endpoint(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "வணக்கம்", "language": "auto"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "reply": "Brud AI chatbot foundation is working.",
        "detected_language": "unknown",
        "model": "placeholder",
        "phase": 9,
    }


async def test_chat_validates_empty_messages(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "", "language": "auto"}
    )
    assert response.status_code == 422


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
