"""MB-29: API tests for /api/admin/mini-brain/local-setup.

Auth/CSRF enforcement per route and real HTTP round-trips through a
real app, real database, and a real temporary allowed model directory.
No public routes exist in this phase.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from core_model.mini_brain.provider_settings import secret_encryptor
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBLC = "/api/admin/mini-brain/local-setup"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def allowed_model_dir(tmp_path: Path) -> Path:
    allowed = tmp_path / "models"
    allowed.mkdir()
    return allowed


@pytest.fixture
def api_app(tmp_path: Path, allowed_model_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    from backend.main import create_app

    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allowed_model_dir=allowed_model_dir, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_all_routes_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBLC}/hardware")).status_code == 401
        assert (await client.get(f"{MBLC}/scan-models")).status_code == 401
        assert (await client.get(f"{MBLC}/recommendations")).status_code == 401
        assert (await client.post(f"{MBLC}/save-local-model", json={})).status_code == 401
        assert (await client.post(f"{MBLC}/save-provider", json={"provider_key": "openai"})).status_code == 401
        assert (await client.get(f"{MBLC}/providers/catalog")).status_code == 401
        assert (await client.get(f"{MBLC}/setup-guide")).status_code == 401
        assert (await client.get(f"{MBLC}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_save_local_model_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLC}/save-local-model", json={})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_save_provider_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLC}/save-provider", json={"provider_key": "openai"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_hardware_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/hardware", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for field in ("total_ram_gb", "cpu_cores", "recommended_ram_tier", "health"):
            assert field in body
    finally:
        await client.aclose()


async def test_scan_models_over_http(api_app: FastAPI, allowed_model_dir: Path) -> None:
    (allowed_model_dir / "model.gguf").write_bytes(b"x")
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/scan-models", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_recommendations_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/recommendations", headers=headers)
        assert response.status_code == 200
        assert response.json()["top_recommendation"] is not None
    finally:
        await client.aclose()


async def test_save_local_model_over_http(api_app: FastAPI, allowed_model_dir: Path) -> None:
    model_file = allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBLC}/save-local-model",
            json={"model_path": str(model_file), "context_length": 4096, "max_tokens": 256, "temperature": 0.4, "threads": 2},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["config"]["context_length"] == 4096
    finally:
        await client.aclose()


async def test_save_local_model_rejects_unconfined_path_over_http(api_app: FastAPI, tmp_path: Path) -> None:
    outside = tmp_path / "outside.gguf"
    outside.write_bytes(b"x")
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBLC}/save-local-model", json={"model_path": str(outside)}, headers=headers,
        )
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_save_provider_over_http_never_echoes_api_key(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBLC}/save-provider",
            json={"provider_key": "openai", "api_key": "sk-http-test-secret", "model": "gpt-4o-mini", "enabled": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert "sk-http-test-secret" not in response.text
    finally:
        await client.aclose()


async def test_save_provider_rejects_unknown_provider_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLC}/save-provider", json={"provider_key": "bogus"}, headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_providers_catalog_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/providers/catalog", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["providers"]) == 4
    finally:
        await client.aclose()


async def test_setup_guide_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/setup-guide", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["steps"]) >= 2
    finally:
        await client.aclose()


async def test_diagnostics_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for field in ("hardware", "scanned_model_count", "configured_model_path", "local_model_available"):
            assert field in body
    finally:
        await client.aclose()


async def test_no_public_route_exists_for_local_setup(api_app: FastAPI) -> None:
    local_setup_paths = [route.path for route in api_app.routes if hasattr(route, "path") and "local-setup" in route.path]
    assert local_setup_paths
    assert all("/admin/" in path for path in local_setup_paths)
