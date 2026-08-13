"""MB-27: API tests for /api/admin/mini-brain/provider-settings.

Auth/CSRF enforcement per route, full HTTP CRUD lifecycle, and a
recursive-dict-walk assertion that no response body anywhere contains
an `encrypted_value` key or the literal secret value used in these
tests. No public routes exist in this phase at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services import mini_brain_provider_settings_service as service_module
from backend.services.provider_settings_connection_adapters import MockConnectionAdapter
from core_model.mini_brain.provider_settings import secret_encryptor
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBPS = "/api/admin/mini-brain/provider-settings"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    key = Fernet.generate_key()
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key.decode("ascii"))
    return key


@pytest.fixture
def api_app(tmp_path: Path, fernet_key: bytes) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _no_forbidden_keys(payload) -> bool:
    forbidden = {"encrypted_value"}
    if isinstance(payload, dict):
        if forbidden & set(payload.keys()):
            return False
        return all(_no_forbidden_keys(value) for value in payload.values())
    if isinstance(payload, list):
        return all(_no_forbidden_keys(item) for item in payload)
    return True


async def test_all_routes_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBPS}/diagnostics")).status_code == 401
        assert (await client.get(f"{MBPS}/providers")).status_code == 401
        assert (await client.post(f"{MBPS}/providers", json={"provider_key": "openai"})).status_code == 401
        assert (await client.get(f"{MBPS}/export")).status_code == 401
        assert (await client.get(f"{MBPS}/memory")).status_code == 401
    finally:
        await client.aclose()


async def test_create_provider_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPS}/providers", json={"provider_key": "openai"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_diagnostics_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPS}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["encryption_available"] is True
        for field in ("encryption_available", "missing_encryption_key", "configured_provider_count", "enabled_provider_count", "provider_health", "unavailable_providers"):
            assert field in body
    finally:
        await client.aclose()


async def test_create_provider_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["provider_key"] == "openai"
        assert _no_forbidden_keys(body)
    finally:
        await client.aclose()


async def test_create_unknown_provider_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPS}/providers", json={"provider_key": "bogus"}, headers=headers)
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_full_crud_lifecycle_over_http(api_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module, "adapter_for_provider",
        lambda provider_key: MockConnectionAdapter(provider_key=provider_key, status="success", latency_ms=2.5),
    )
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        assert created.status_code == 200, created.text
        setting_id = created.json()["public_id"]

        fetched = await client.get(f"{MBPS}/providers/{setting_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["provider_key"] == "openai"

        secret_set = await client.post(
            f"{MBPS}/providers/{setting_id}/secrets",
            json={"secret_name": "api_key", "value": "sk-super-secret-http-test-value"},
            headers=headers,
        )
        assert secret_set.status_code == 200, secret_set.text
        assert "sk-super-secret-http-test-value" not in json.dumps(secret_set.json())
        assert secret_set.json()["secrets"][0]["is_set"] is True

        enabled = await client.post(f"{MBPS}/providers/{setting_id}/enable", headers=headers)
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True

        tested = await client.post(f"{MBPS}/providers/{setting_id}/test", json={}, headers=headers)
        assert tested.status_code == 200, tested.text
        assert tested.json()["status"] == "success"
        assert "sk-super-secret-http-test-value" not in json.dumps(tested.json())

        updated = await client.patch(f"{MBPS}/providers/{setting_id}", json={"config": {"model": "gpt-4o-mini"}}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["config"] == {"model": "gpt-4o-mini"}

        disabled = await client.post(f"{MBPS}/providers/{setting_id}/disable", headers=headers)
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        deleted = await client.delete(f"{MBPS}/providers/{setting_id}/secrets/api_key", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["secrets"] == []

        audit = await client.get(f"{MBPS}/providers/{setting_id}/audit", headers=headers)
        assert audit.status_code == 200
        assert len(audit.json()["items"]) >= 4

        archived = await client.post(f"{MBPS}/providers/{setting_id}/archive", headers=headers)
        assert archived.status_code == 200

        memory = await client.get(f"{MBPS}/memory", headers=headers)
        assert memory.status_code == 200
        assert len(memory.json()["items"]) >= 1

        listed = await client.get(f"{MBPS}/providers", headers=headers)
        assert listed.status_code == 200
        # archived provider excluded from default listing
        assert setting_id not in [item["public_id"] for item in listed.json()["items"]]
    finally:
        await client.aclose()


async def test_export_over_http_excludes_secrets(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "anthropic", "enabled": True, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        await client.post(
            f"{MBPS}/providers/{setting_id}/secrets", json={"secret_name": "api_key", "value": "sk-export-test-value"}, headers=headers,
        )
        exported = await client.get(f"{MBPS}/export", headers=headers)
        assert exported.status_code == 200
        body = exported.json()
        assert "sk-export-test-value" not in json.dumps(body)
        assert _no_forbidden_keys(body)
        assert "secrets" not in json.dumps(body)
    finally:
        await client.aclose()


async def test_import_metadata_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "gemini", "enabled": True, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        imported = await client.post(
            f"{MBPS}/import-metadata", json={"providers": [{"provider_key": "gemini", "enabled": False}]}, headers=headers,
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["items"][0]["enabled"] is False
        _ = setting_id
    finally:
        await client.aclose()


async def test_import_metadata_rejects_encrypted_value_field(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBPS}/import-metadata", json={"providers": [{"provider_key": "openai", "encrypted_value": "x"}]}, headers=headers,
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_no_response_body_across_lifecycle_contains_encrypted_value(api_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module, "adapter_for_provider",
        lambda provider_key: MockConnectionAdapter(provider_key=provider_key, status="success"),
    )
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openrouter", "enabled": True, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        responses = [
            created,
            await client.post(f"{MBPS}/providers/{setting_id}/secrets", json={"secret_name": "api_key", "value": "sk-recursive-scan-value"}, headers=headers),
            await client.get(f"{MBPS}/providers/{setting_id}", headers=headers),
            await client.get(f"{MBPS}/providers", headers=headers),
            await client.post(f"{MBPS}/providers/{setting_id}/test", json={}, headers=headers),
            await client.get(f"{MBPS}/export", headers=headers),
            await client.get(f"{MBPS}/diagnostics", headers=headers),
        ]
        for response in responses:
            body = response.json()
            assert _no_forbidden_keys(body), f"forbidden key found in {response.request.url}: {body}"
            assert "sk-recursive-scan-value" not in json.dumps(body)
    finally:
        await client.aclose()


async def test_get_missing_provider_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPS}/providers/00000000-0000-0000-0000-000000000000", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_test_connection_missing_key_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": True, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        response = await client.post(f"{MBPS}/providers/{setting_id}/test", json={}, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "missing_key"
    finally:
        await client.aclose()


async def test_set_secret_empty_value_rejected_by_model_validation(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        response = await client.post(f"{MBPS}/providers/{setting_id}/secrets", json={"secret_name": "api_key", "value": ""}, headers=headers)
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_disable_then_enable_provider_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "faster_whisper", "enabled": True, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        disabled = await client.post(f"{MBPS}/providers/{setting_id}/disable", headers=headers)
        assert disabled.json()["enabled"] is False
        re_enabled = await client.post(f"{MBPS}/providers/{setting_id}/enable", headers=headers)
        assert re_enabled.json()["enabled"] is True
    finally:
        await client.aclose()


async def test_secrets_route_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        response = await client.post(f"{MBPS}/providers/{setting_id}/secrets", json={"secret_name": "api_key", "value": "sk-x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_archive_route_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        response = await client.post(f"{MBPS}/providers/{setting_id}/archive")
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_memory_and_audit_routes_support_pagination_params(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": False, "config": {}}, headers=headers)
        setting_id = created.json()["public_id"]
        memory = await client.get(f"{MBPS}/memory?limit=10&offset=0", headers=headers)
        assert memory.status_code == 200
        audit = await client.get(f"{MBPS}/providers/{setting_id}/audit?limit=10&offset=0", headers=headers)
        assert audit.status_code == 200
    finally:
        await client.aclose()


async def test_list_providers_filters_by_enabled(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MBPS}/providers", json={"provider_key": "openai", "enabled": True, "config": {}}, headers=headers)
        await client.post(f"{MBPS}/providers", json={"provider_key": "anthropic", "enabled": False, "config": {}}, headers=headers)
        response = await client.get(f"{MBPS}/providers?enabled=true", headers=headers)
        assert response.status_code == 200
        keys = {item["provider_key"] for item in response.json()["items"]}
        assert keys == {"openai"}
    finally:
        await client.aclose()
