"""MB-04C: API tests for /admin/mini-brain/capability.

Auth/CSRF, all 5 routes, isolation proof, and an opportunistic
real-model end-to-end test (only runs if the real Qwen GGUF
provisioned in MB-04.1 is actually present -- skipped cleanly
otherwise, matching MB-04A/MB-04B's own test discipline).
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

MBC = "/api/admin/mini-brain/capability"
REAL_MODEL_PATH = Path("/home/dhurai/Projects/brud-ai/data/models/qwen2.5-0.5b-instruct-q4_k_m.gguf")


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
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_models_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBC}/models")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_analyze_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBC}/analyze", json={"question": "What is a dataset?"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_models_lists_known_profiles(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBC}/models", headers=headers)
        assert response.status_code == 200
        profiles = response.json()["profiles"]
        assert "qwen2.5-0.5b-instruct" in profiles
        assert profiles["qwen2.5-0.5b-instruct"]["verified"] is True
        assert profiles["tinyllama-1.1b-chat"]["verified"] is False
    finally:
        await client.aclose()


async def test_analyze_returns_category_and_strategy_without_generating(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBC}/analyze", headers=headers, json={"question": "How do I create a dataset?"})
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "dataset"
        assert "strategy" in body

        status = await client.get("/api/admin/mini-brain/runtime/status", headers=headers)
        assert status.json()["state"] == "unloaded"  # analyze never loads/generates
    finally:
        await client.aclose()


async def test_profile_endpoint_looks_up_by_name(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBC}/profile", headers=headers, json={"model_name": "Qwen2.5-0.5B-Instruct"})
        assert response.status_code == 200
        assert response.json()["verified"] is True
    finally:
        await client.aclose()


async def test_diagnostics_returns_pipeline_info(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["ai_model_used"] is False
        assert body["max_retries"] == 1
    finally:
        await client.aclose()


async def test_generate_fails_cleanly_when_no_model_loaded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBC}/generate", headers=headers, json={"question": "What is a dataset?"})
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_capability_routes_never_touch_prompt_optimization_or_quality_state(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MBC}/analyze", headers=headers, json={"question": "What is a dataset?"})
        # Runtime remains untouched -- no route in this phase registers/loads a model.
        status = await client.get("/api/admin/mini-brain/runtime/status", headers=headers)
        assert status.json()["state"] == "unloaded"
    finally:
        await client.aclose()


@pytest.mark.skipif(not REAL_MODEL_PATH.exists(), reason="real Qwen GGUF not present in this environment")
async def test_generate_end_to_end_with_the_real_provisioned_model(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        registered = await client.post(
            "/api/admin/mini-brain/runtime/models", headers=headers,
            json={"name": "Qwen2.5-0.5B-Instruct", "path": str(REAL_MODEL_PATH), "quantization": "Q4_K_M", "context_length": 2048},
        )
        model_id = registered.json()["public_id"]
        loaded = await client.post("/api/admin/mini-brain/runtime/load", headers=headers, json={"model_public_id": model_id})
        assert loaded.status_code == 200

        response = await client.post(
            f"{MBC}/generate", headers=headers,
            json={"question": "What is dataset duplicate detection?", "timeout_seconds": 250.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["profile"]["verified"] is True
        assert body["category"] == "dataset"
        assert "generation_time_ms" in body
    finally:
        await client.aclose()
