"""MB-21: API tests for /admin/mini-brain/external-ai-gateway.

Auth/CSRF requirements and route wiring over real HTTP. The full
12-stage workflow with successful mock providers is already proven at
the service layer in test_mini_brain_external_ai_gateway_service.py --
this file confirms the routes correctly translate HTTP requests into
those same service calls, using the real (but honestly unavailable in
this environment -- no API key configured) OpenRouter client the route
layer constructs by default. No real network call is ever made: with
no `BRUD_EXTERNAL_AI_OPENROUTER_API_KEY` set, `is_available()` is
`False` and `dispatch()` short-circuits before any HTTP request.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

GA = "/api/admin/mini-brain/external-ai-gateway"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{GA}/sessions")).status_code == 401
        assert (await client.get(f"{GA}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_training_no_deployment(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{GA}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["training_started"] is False
        assert body["model_deployed"] is False
        assert body["dataset_approved"] is False
        assert body["release_approved"] is False
        assert body["shell_commands_executed"] is False
        assert body["executable_files_downloaded"] is False
        assert body["provider_calls_require_authorization"] is True
        assert body["automatic_approval"] is False
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{GA}/sessions", json={"topic": "hello", "purpose": "public_style_stress_test"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_workflow_over_http_with_unavailable_provider(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{GA}/sessions", json={"topic": "http workflow", "purpose": "public_style_stress_test"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["public_id"]
        assert response.json()["stage"] == "validate_authorization"

        response = await client.post(
            f"{GA}/sessions/{session_id}/authorize", json={"authorization_note": "http workflow test"}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "sanitize_inputs"

        response = await client.post(f"{GA}/sessions/{session_id}/sanitize", json={}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "select_providers"

        response = await client.post(
            f"{GA}/sessions/{session_id}/select-providers", json={"requested_provider_keys": ["openrouter"]}, headers=headers,
        )
        # openrouter is genuinely unavailable in this test environment (no API key) --
        # select-providers must honestly reject with no enabled provider, never fabricate one.
        assert response.status_code in (400, 422), response.text
    finally:
        await client.aclose()


async def test_dispatch_before_authorization_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{GA}/sessions", json={"topic": "out of order", "purpose": "public_style_stress_test"}, headers=headers,
        )
        session_id = response.json()["public_id"]

        response = await client.post(f"{GA}/sessions/{session_id}/dispatch", json={}, headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{GA}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_list_sessions_and_memory_routes(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{GA}/sessions", headers=headers)
        assert response.status_code == 200
        response = await client.get(f"{GA}/memory", headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_authorization_with_empty_note_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{GA}/sessions", json={"topic": "t", "purpose": "public_style_stress_test"}, headers=headers,
        )
        session_id = response.json()["public_id"]
        # Pydantic's own min_length=1 rejects an empty string at the model layer.
        response = await client.post(f"{GA}/sessions/{session_id}/authorize", json={"authorization_note": ""}, headers=headers)
        assert response.status_code == 422
    finally:
        await client.aclose()
