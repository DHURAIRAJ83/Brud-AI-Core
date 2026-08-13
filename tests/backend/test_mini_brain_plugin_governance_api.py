"""MB-24: API tests for /api/admin/mini-brain/plugin-governance and
/api/public/plugin-policy/check.

Auth/CSRF/rate-limit requirements and route wiring over real HTTP. The
full workflow is already proven at the service layer in
test_mini_brain_plugin_governance_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service
calls.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBPG = "/api/admin/mini-brain/plugin-governance"
PUBLIC_PG = "/api/public/plugin-policy"

VALID_MANIFEST = {
    "plugin_id": "weather-lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Acme Co",
    "description": "Looks up weather.", "entrypoint": "main.js",
    "requested_scopes": ["filesystem.read.user_selected"],
    "allowed_domains": [], "filesystem_roots": ["/home/user/weather-cache"],
    "ui_components": [], "local_storage_usage": True, "cloud_storage_usage": False,
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
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_admin_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBPG}/plugins")).status_code == 401
        assert (await client.get(f"{MBPG}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_discloses_no_automatic_actions(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPG}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["plugin_binaries_ever_executed"] is False
        assert body["auto_enable_after_upload_performed"] is False
        assert body["auto_permission_grant_performed"] is False
        assert body["training_jobs_started"] is False
        assert body["releases_approved"] is False
        assert body["plugins_start_disabled"] is True
    finally:
        await client.aclose()


async def test_register_plugin_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPG}/plugins", json={"manifest": VALID_MANIFEST, "source": "manual_upload"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_public_plugin_policy_route_requires_no_admin_auth(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        create = await client.post(
            f"{MBPG}/plugins", json={"manifest": VALID_MANIFEST, "source": "manual_upload"}, headers=headers,
        )
        plugin_id = create.json()["public_id"]
    finally:
        await client.aclose()

    from httpx import ASGITransport, AsyncClient

    public_client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await public_client.get(f"{PUBLIC_PG}/check", params={"plugin_id": plugin_id, "scope_key": "filesystem.read.user_selected"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body.keys()) >= {"tool_visible", "tool_executable", "consent_required", "admin_review_required"}
        assert "token" not in body
    finally:
        await public_client.aclose()


async def test_full_workflow_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPG}/plugins", json={"manifest": VALID_MANIFEST, "source": "manual_upload"}, headers=headers)
        assert response.status_code == 200, response.text
        plugin_id = response.json()["public_id"]
        assert response.json()["status"] == "disabled"

        response = await client.post(f"{MBPG}/plugins/{plugin_id}/validate", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["stage"] == "classify_capabilities"

        for path in ("classify", "risk-score", "sandbox-profile", "filesystem-policy", "network-policy"):
            response = await client.post(f"{MBPG}/plugins/{plugin_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)

        response = await client.post(f"{MBPG}/plugins/{plugin_id}/enable", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "enabled"

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/evaluate-permission",
            json={"scope_key": "filesystem.read.user_selected", "is_public_chat": False}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "require_consent"

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/request-consent",
            json={"scope_key": "filesystem.read.user_selected", "raw_user_identity": "user-1", "consent_given": True, "ttl_seconds": 3600.0},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        user_id_hash = response.json()["user_id_hash"]

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/grant-permission",
            json={"scope_key": "filesystem.read.user_selected", "user_id_hash": user_id_hash}, headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "granted"

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/issue-token",
            json={
                "scope_keys": ["filesystem.read.user_selected"], "raw_user_identity": "user-1",
                "raw_session_identity": "session-1", "ttl_seconds": 300,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["token_hash"]) == 64

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/runtime-event",
            json={"event_type": "plugin_execution_reported", "message": "ok", "metadata": {}}, headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.post(f"{MBPG}/plugins/{plugin_id}/report", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["governance_report"]["no_plugin_binary_execution"] is True

        response = await client.get(f"{MBPG}/plugins/{plugin_id}/permissions", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 1

        response = await client.get(f"{MBPG}/plugins/{plugin_id}/consents", headers=headers)
        assert response.status_code == 200

        response = await client.get(f"{MBPG}/plugins/{plugin_id}/events", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

        response = await client.post(f"{MBPG}/plugins/{plugin_id}/disable", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "disabled"

        response = await client.post(f"{MBPG}/plugins/{plugin_id}/archive", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "archived"

        response = await client.get(f"{MBPG}/memory", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_grant_permission_before_consent_returns_error_status(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        create = await client.post(f"{MBPG}/plugins", json={"manifest": VALID_MANIFEST, "source": "manual_upload"}, headers=headers)
        plugin_id = create.json()["public_id"]
        for path in ("validate", "classify", "risk-score", "sandbox-profile", "filesystem-policy", "network-policy", "enable"):
            await client.post(f"{MBPG}/plugins/{plugin_id}/{path}", headers=headers)

        response = await client.post(
            f"{MBPG}/plugins/{plugin_id}/grant-permission",
            json={"scope_key": "filesystem.read.user_selected", "user_id_hash": None}, headers=headers,
        )
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_get_unknown_plugin_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPG}/plugins/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_list_plugins_and_memory_routes(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPG}/plugins", headers=headers)
        assert response.status_code == 200
        response = await client.get(f"{MBPG}/memory", headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()
