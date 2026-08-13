"""MB-04: CPU Runtime -- API tests.

Exercises the real HTTP routes with the real (production) backend
factory, `LlamaCppBackend`, proving a corrupted/fake model file fails
honestly end-to-end over HTTP. As of MB-04.1, `llama-cpp-python` is
installed in this environment; the "library not installed" honest
failure is covered at the service level in
`test_mini_brain_runtime_service.py` via `UnavailableFakeBackend`,
which remains valid regardless of what's installed on this machine.
Full real-model lifecycle (register/load/generate/unload against an
actual GGUF file) is exercised by the MB-04.1 provisioning scripts,
not by this always-run suite, since it depends on a downloaded model
file that isn't part of the repository.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.services.mini_brain_runtime_manager_service import reset_runtime_for_tests
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBRT = "/api/admin/mini-brain/runtime"


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_runtime_for_tests()
    yield
    reset_runtime_for_tests()


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


@pytest.fixture
def fixture_model_path(tmp_path: Path) -> str:
    path = tmp_path / "fake-test-model.gguf"
    path.write_bytes(b"NOT A REAL MODEL -- test fixture only" * 50)
    return str(path)


async def test_status_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBRT}/status")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_register_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBRT}/models", json={"name": "X", "path": "/x.gguf", "quantization": "Q4_K_M", "context_length": 2048},
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_status_before_anything_registered(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRT}/status", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "unloaded"
        assert body["current_model"] is None
    finally:
        await client.aclose()


async def test_register_and_list_model(api_app: FastAPI, fixture_model_path: str) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBRT}/models", headers=headers,
            json={"name": "Test Model", "path": fixture_model_path, "quantization": "Q4_K_M", "context_length": 2048},
        )
        assert response.status_code == 200, response.text
        model_id = response.json()["public_id"]

        listed = await client.get(f"{MBRT}/models", headers=headers)
        assert len(listed.json()["items"]) == 1

        info = await client.get(f"{MBRT}/models/{model_id}", headers=headers)
        assert info.status_code == 200
        assert info.json()["file_exists"] is True
        assert info.json()["validation_issues"] == []
    finally:
        await client.aclose()


async def test_register_rejects_missing_file(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBRT}/models", headers=headers,
            json={"name": "X", "path": "/nonexistent/file.gguf", "quantization": "Q4_K_M", "context_length": 2048},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_load_honestly_fails_with_corrupted_model_file(api_app: FastAPI, fixture_model_path: str) -> None:
    """The real, production LlamaCppBackend against a `.gguf`-named file
    that isn't a real model (MB-04.1: llama-cpp-python is installed in
    this environment as of the real-model provisioning phase, so a
    corrupted/fake file is now the honest way to exercise this failure
    path -- the earlier "library not installed" case is covered at the
    service level in test_mini_brain_runtime_service.py via
    UnavailableFakeBackend, which stays valid regardless of what's
    installed on this machine)."""

    client, headers = await authenticated_client(api_app)
    try:
        registered = await client.post(
            f"{MBRT}/models", headers=headers,
            json={"name": "Test Model", "path": fixture_model_path, "quantization": "Q4_K_M", "context_length": 2048},
        )
        model_id = registered.json()["public_id"]

        loaded = await client.post(f"{MBRT}/load", headers=headers, json={"model_public_id": model_id})
        assert loaded.status_code == 422
        assert "model load failed" in loaded.json()["error"]["message"]

        status = await client.get(f"{MBRT}/status", headers=headers)
        assert status.json()["state"] == "error"

        health = await client.get(f"{MBRT}/health", headers=headers)
        assert health.json()["status"] == "unhealthy"
    finally:
        await client.aclose()


async def test_generate_without_response_plan_is_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBRT}/generate", headers=headers,
            json={"response_plan": {"just_text": "answer this"}},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_diagnostics_and_statistics_available_with_no_model(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        diag = await client.get(f"{MBRT}/diagnostics", headers=headers)
        assert diag.status_code == 200
        assert diag.json()["registered_model_count"] == 0

        stats = await client.get(f"{MBRT}/statistics", headers=headers)
        assert stats.status_code == 200
        assert stats.json()["total_generations"] == 0
        assert "process_cpu_time_seconds" in stats.json()
    finally:
        await client.aclose()


async def test_runtime_never_touches_knowledge_core_admin_assistant_or_public_chat(
    api_app: FastAPI, fixture_model_path: str,
) -> None:
    from backend.database.connection import database_connection

    client, headers = await authenticated_client(api_app)
    try:
        registered = await client.post(
            f"{MBRT}/models", headers=headers,
            json={"name": "Test Model", "path": fixture_model_path, "quantization": "Q4_K_M", "context_length": 2048},
        )
        model_id = registered.json()["public_id"]
        await client.post(f"{MBRT}/load", headers=headers, json={"model_public_id": model_id})
        await client.post(f"{MBRT}/generate", headers=headers, json={"response_plan": {"x": 1}})
        await client.get(f"{MBRT}/diagnostics", headers=headers)
    finally:
        await client.aclose()

    with database_connection(api_app.state.settings.resolved_database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM inference_model_assignments"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM mini_brain_knowledge_items"
        ).fetchone()[0] == 0
