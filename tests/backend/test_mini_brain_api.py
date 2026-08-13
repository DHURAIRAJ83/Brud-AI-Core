"""MB-01: Brud Mini Brain -- foundation API tests.

Covers the framework skeleton only (no model exists to test): module
lifecycle (enable/disable), settings, health, diagnostics, logs, and
that every placeholder interface is honest about not being
implemented rather than fabricating a result.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MB = "/api/admin/mini-brain"


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


async def test_status_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MB}/status")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_default_state_is_disabled_and_stopped(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MB}/status", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is False
        assert body["runtime_status"] == "stopped"
        assert body["health"]["status"] == "disabled"
        assert body["version"]["model"] is None
        assert body["version"]["model_status"] == "not_integrated"
    finally:
        await client.aclose()


async def test_enable_then_disable_lifecycle(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        enabled = await client.post(f"{MB}/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["enabled"] is True
        assert enabled.json()["runtime_status"] == "running"

        health = await client.get(f"{MB}/health", headers=headers)
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        disabled = await client.post(f"{MB}/disable", headers=headers)
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["enabled"] is False
        assert disabled.json()["runtime_status"] == "stopped"
    finally:
        await client.aclose()


async def test_enable_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MB}/enable")
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_settings_update_rejects_invalid_runtime_backend(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.patch(
            f"{MB}/settings", headers=headers,
            json={"config": {"runtime_backend": "ollama"}},
        )
        assert response.status_code == 422, response.text
    finally:
        await client.aclose()


async def test_settings_update_accepts_valid_log_level(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.patch(
            f"{MB}/settings", headers=headers, json={"config": {"log_level": "debug"}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["config"]["log_level"] == "debug"
        assert response.json()["config"]["runtime_backend"] == "none"
    finally:
        await client.aclose()


async def test_diagnostics_reports_no_model_integrated(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MB}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["model_integrated"] is False
        assert body["config_issues"] == []
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/inference"), ("GET", "/knowledge"), ("GET", "/memory"),
        ("POST", "/suggestions"), ("GET", "/context"),
    ],
)
async def test_every_placeholder_interface_is_honest_not_implemented(
    api_app: FastAPI, method: str, path: str,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.request(method, f"{MB}{path}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["available"] is False
        assert body["reason"] == "not_implemented_in_mb01"
    finally:
        await client.aclose()


async def test_actions_are_logged_and_visible_in_logs(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MB}/enable", headers=headers)
        await client.get(f"{MB}/knowledge", headers=headers)
        logs = await client.get(f"{MB}/logs", headers=headers)
        assert logs.status_code == 200
        body = logs.json()
        event_types = {item["event_type"] for item in body["items"]}
        assert "module_enabled" in event_types
        assert "runtime_started" in event_types
        assert "placeholder_call" in event_types
    finally:
        await client.aclose()


async def test_mini_brain_never_touches_admin_assistant_tables(api_app: FastAPI) -> None:
    """Direct proof of independence: enabling/disabling Mini Brain and
    calling every placeholder interface must not create any row in
    admin_approvals (the Admin Assistant's own proposal table)."""

    from backend.database.connection import database_connection

    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MB}/enable", headers=headers)
        await client.post(f"{MB}/inference", headers=headers)
        await client.post(f"{MB}/suggestions", headers=headers)
        await client.post(f"{MB}/disable", headers=headers)
    finally:
        await client.aclose()

    with database_connection(api_app.state.settings.resolved_database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0]
        assert count == 0
