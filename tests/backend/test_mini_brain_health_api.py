"""MB-31G: API tests for /api/admin/mini-brain/runtime-health.

Real HTTP round-trips through a real app + real database. Never
`/admin/mini-brain/health` -- that path already belongs to the MB-01
placeholder module (backend/api/routes/mini_brain.py); this endpoint
is deliberately named "runtime-health" to stay collision-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBH = "/api/admin/mini-brain"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allowed_model_dir=tmp_path / "models", allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_runtime_health_requires_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBH}/runtime-health")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_runtime_health_does_not_collide_with_legacy_health(api_app: FastAPI) -> None:
    """The MB-01 placeholder module already owns /admin/mini-brain/health --
    this new endpoint must live at a distinct path, never shadow it."""
    client, headers = await authenticated_client(api_app)
    try:
        legacy = await client.get(f"{MBH}/health", headers=headers)
        runtime = await client.get(f"{MBH}/runtime-health", headers=headers)
        assert legacy.status_code == 200
        assert runtime.status_code == 200
        assert legacy.json() != runtime.json()
        assert "status" in legacy.json()
        assert "backend_type" in runtime.json()
    finally:
        await client.aclose()


async def test_runtime_health_shape_when_nothing_configured(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBH}/runtime-health", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["model_loaded"] is False
        assert body["model_id"] is None
        assert body["configured_model_path_masked"] is None
        assert body["benchmark_rating"] is None
        assert body["tokens_per_second"] is None
        assert body["external_provider_enabled"] is False
        assert body["tamil_quality_status"] is None
        assert body["english_quality_status"] is None
        assert isinstance(body["available_ram_gb"], (int, float))
        assert "en" in body["next_action"] and "ta" in body["next_action"]
    finally:
        await client.aclose()


async def test_runtime_health_never_leaks_full_filesystem_path(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBH}/runtime-health", headers=headers)
        body = response.json()
        masked = body["configured_model_path_masked"]
        if masked is not None:
            assert "/" not in masked and "\\" not in masked
    finally:
        await client.aclose()
