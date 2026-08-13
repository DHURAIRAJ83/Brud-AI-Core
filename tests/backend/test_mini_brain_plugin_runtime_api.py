"""MB-25: API tests for /api/admin/mini-brain/plugin-runtime and
/api/public/plugin-runtime/execute.

Auth/CSRF/rate-limit requirements and route wiring over real HTTP,
using the real `weather_lookup` reference plugin package. The full
workflow is already proven at the service layer in
test_mini_brain_plugin_runtime_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service
calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBPR = "/api/admin/mini-brain/plugin-runtime"
PUBLIC_PR = "/api/public/plugin-runtime"
REAL_PLUGIN_DIR = Path(__file__).resolve().parents[2] / "data" / "plugins"

GOVERNANCE_MANIFEST = {
    "plugin_id": "weather_lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Brud AI",
    "description": "Deterministic stub weather lookup.", "entrypoint": "main.py",
    "requested_scopes": ["network.http.allowed_domains"], "allowed_domains": ["api.weather.example"],
    "filesystem_roots": [], "ui_components": [], "local_storage_usage": False, "cloud_storage_usage": False,
    "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned", "homepage": "https://example.com",
    "support_url": "https://example.com/support",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", plugin_package_dir=REAL_PLUGIN_DIR,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _approve_and_enable_and_grant(settings) -> tuple[str, dict]:
    gov = MiniBrainPluginGovernanceService(settings)
    plugin = gov.register_plugin(manifest=GOVERNANCE_MANIFEST, admin_id="admin-1")
    plugin_id = plugin["public_id"]
    gov.run_validate_manifest_stage(plugin_id, admin_id="admin-1")
    gov.run_classify_capabilities_stage(plugin_id, admin_id="admin-1")
    gov.run_compute_risk_stage(plugin_id, admin_id="admin-1")
    gov.run_build_sandbox_stage(plugin_id, admin_id="admin-1")
    gov.run_build_filesystem_policy_stage(plugin_id, admin_id="admin-1")
    gov.run_build_network_policy_stage(plugin_id, admin_id="admin-1")
    gov.enable_plugin(plugin_id, admin_id="admin-1")
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")
    return plugin_id, token


async def test_admin_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBPR}/executions")).status_code == 401
        assert (await client.get(f"{MBPR}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_bypass(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPR}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["plugins_executed_without_mb24_approval"] is False
        assert body["consent_bypassed"] is False
        assert body["shell_commands_executed"] is False
        assert body["container_isolation_exists"] is False
    finally:
        await client.aclose()


async def test_execute_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPR}/execute", json={"plugin_public_id": "x", "scope_key": "y", "arguments": {}, "execution_token": {"payload": {}, "token_hash": "z"}})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_full_admin_workflow_over_http(api_app: FastAPI) -> None:
    plugin_id, token = _approve_and_enable_and_grant(api_app.state.settings)
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBPR}/execute",
            json={"plugin_public_id": plugin_id, "scope_key": "network.http.allowed_domains", "arguments": {"location": "London"}, "execution_token": token, "timeout_seconds": 5.0},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        execution = response.json()
        assert execution["status"] == "completed"
        execution_id = execution["public_id"]

        response = await client.get(f"{MBPR}/executions/{execution_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = await client.get(f"{MBPR}/executions/{execution_id}/logs", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["io"]) == 2
        assert len(response.json()["events"]) > 0

        response = await client.post(f"{MBPR}/executions/{execution_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["no_container_isolation"] is True

        response = await client.post(f"{MBPR}/executions/{execution_id}/runtime-event", json={"event_type": "note", "message": "reviewed", "metadata": {}}, headers=headers)
        assert response.status_code == 200, response.text

        response = await client.post(f"{MBPR}/executions/{execution_id}/archive", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "archived"

        response = await client.get(f"{MBPR}/memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

        response = await client.get(f"{MBPR}/statistics", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_executions"] >= 1

        response = await client.get(f"{MBPR}/executions", headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_public_execute_requires_no_admin_auth(api_app: FastAPI) -> None:
    plugin_id, token = _approve_and_enable_and_grant(api_app.state.settings)
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(
            f"{PUBLIC_PR}/execute",
            json={"plugin_public_id": plugin_id, "scope_key": "network.http.allowed_domains", "arguments": {"location": "London"}, "raw_user_identity": "user-1", "execution_token": token},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
    finally:
        await client.aclose()


async def test_public_execute_with_invalid_token_is_denied_not_500(api_app: FastAPI) -> None:
    plugin_id, _token = _approve_and_enable_and_grant(api_app.state.settings)
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(
            f"{PUBLIC_PR}/execute",
            json={"plugin_public_id": plugin_id, "scope_key": "network.http.allowed_domains", "arguments": {}, "raw_user_identity": "user-1", "execution_token": {"payload": {"plugin_id": plugin_id, "granted_scopes": [], "issued_at": 0, "expires_at": 0, "user_id_hash": "x", "session_id_hash": "y", "nonce": "z"}, "token_hash": "0" * 64}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "denied"
    finally:
        await client.aclose()


async def test_get_unknown_execution_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPR}/executions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()
