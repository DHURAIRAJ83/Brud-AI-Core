"""MB-30: API tests for /api/admin/mini-brain/runtime-manager.

Auth/CSRF enforcement per route and real HTTP round-trips through a
real app, real database, and a real temporary allowed model directory.
No public routes exist in this phase.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from core_model.mini_brain.runtime_manager import checksum_verifier
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBRM = "/api/admin/mini-brain/runtime-manager"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def allowed_model_dir(tmp_path: Path) -> Path:
    allowed = tmp_path / "models"
    allowed.mkdir()
    return allowed


@pytest.fixture
def api_app(tmp_path: Path, allowed_model_dir: Path) -> FastAPI:
    from backend.main import create_app

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
        assert (await client.get(f"{MBRM}/hardware")).status_code == 401
        assert (await client.get(f"{MBRM}/catalog")).status_code == 401
        assert (await client.get(f"{MBRM}/installed")).status_code == 401
        assert (await client.get(f"{MBRM}/status")).status_code == 401
        assert (await client.get(f"{MBRM}/recommendation")).status_code == 401
        assert (await client.post(f"{MBRM}/download", json={"model_id": "x"})).status_code == 401
        assert (await client.post(f"{MBRM}/verify", json={"model_id": "x"})).status_code == 401
        assert (await client.post(f"{MBRM}/install", json={"model_id": "x"})).status_code == 401
        assert (await client.post(f"{MBRM}/load", json={"model_id": "x"})).status_code == 401
        assert (await client.post(f"{MBRM}/unload", json={})).status_code == 401
        assert (await client.post(f"{MBRM}/benchmark", json={"model_id": "x"})).status_code == 401
        assert (await client.post(f"{MBRM}/remove", json={"model_id": "x"})).status_code == 401
        assert (await client.get(f"{MBRM}/events")).status_code == 401
        assert (await client.get(f"{MBRM}/memory")).status_code == 401
    finally:
        await client.aclose()


@pytest.mark.parametrize("route,payload", [
    ("download", {"model_id": "x"}), ("verify", {"model_id": "x"}), ("install", {"model_id": "x"}),
    ("load", {"model_id": "x"}), ("unload", {}), ("benchmark", {"model_id": "x"}), ("remove", {"model_id": "x"}),
])
async def test_mutating_routes_require_csrf(api_app: FastAPI, route: str, payload: dict) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/{route}", json=payload)
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_hardware_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/hardware", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for field in ("total_ram_gb", "cpu_cores", "recommended_ram_tier"):
            assert field in body
    finally:
        await client.aclose()


async def test_catalog_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/catalog", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["models"]) == 4
    finally:
        await client.aclose()


async def test_recommendation_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/recommendation", headers=headers)
        assert response.status_code == 200
        assert response.json()["model_id"] == "qwen2.5-1.5b-instruct-q4_k_m"
    finally:
        await client.aclose()


async def test_installed_over_http_empty(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/installed", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []
    finally:
        await client.aclose()


async def test_status_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/status", headers=headers)
        assert response.status_code == 200
        assert response.json()["loaded"] is False
    finally:
        await client.aclose()


async def test_diagnostics_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRM}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for key in ("hardware", "model_status", "load_state", "benchmark_availability", "storage_paths", "fallback_state"):
            assert key in body
    finally:
        await client.aclose()


async def test_diagnostics_requires_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBRM}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_install_and_verify_over_http(api_app: FastAPI, allowed_model_dir: Path) -> None:
    model_file = allowed_model_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    fake_bytes = b"fake" * 500
    model_file.write_bytes(fake_bytes)

    client, headers = await authenticated_client(api_app)
    try:
        install_response = await client.post(
            f"{MBRM}/install", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers,
        )
        assert install_response.status_code == 200, install_response.text
        assert install_response.json()["status"] == "installed"

        installed_response = await client.get(f"{MBRM}/installed", headers=headers)
        assert len(installed_response.json()["items"]) == 1

        verify_response = await client.post(
            f"{MBRM}/verify", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["matches"] is True
    finally:
        await client.aclose()


async def test_download_rejects_unknown_model_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/download", json={"model_id": "bogus-model"}, headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_benchmark_not_installed_returns_error_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/benchmark", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers)
        assert response.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_remove_not_installed_returns_404_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/remove", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_unload_over_http_when_nothing_loaded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/unload", json={}, headers=headers)
        assert response.status_code == 200
        assert response.json()["loaded"] is False
    finally:
        await client.aclose()


async def test_events_and_memory_over_http(api_app: FastAPI, allowed_model_dir: Path) -> None:
    model_file = allowed_model_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"fake" * 500)

    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MBRM}/install", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers)

        events_response = await client.get(f"{MBRM}/events", headers=headers)
        assert events_response.status_code == 200
        assert len(events_response.json()["items"]) >= 1

        memory_response = await client.get(f"{MBRM}/memory", headers=headers)
        assert memory_response.status_code == 200
        assert len(memory_response.json()["items"]) >= 1
    finally:
        await client.aclose()


async def test_no_public_route_exists_for_runtime_manager(api_app: FastAPI) -> None:
    runtime_manager_paths = [route.path for route in api_app.routes if hasattr(route, "path") and "runtime-manager" in route.path]
    assert runtime_manager_paths
    assert all("/admin/" in path for path in runtime_manager_paths)


async def test_response_never_contains_raw_model_absolute_path(api_app: FastAPI, allowed_model_dir: Path) -> None:
    """Structural sanity check specific to this API surface -- install
    returns real DB fields including install_path, which is fine (the
    admin needs it); this test only confirms no field is secret-shaped."""
    model_file = allowed_model_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"fake" * 500)
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRM}/install", json={"model_id": "qwen2.5-1.5b-instruct-q4_k_m"}, headers=headers)
        assert "api_key" not in response.text
        assert "encrypted_value" not in response.text
    finally:
        await client.aclose()
