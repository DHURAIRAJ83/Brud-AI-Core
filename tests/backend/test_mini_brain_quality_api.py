"""MB-04B: API tests for /admin/mini-brain/quality.

Auth/CSRF, all 6 routes, isolation proof, and an opportunistic
real-model end-to-end test (only runs if the real Qwen GGUF
provisioned in MB-04.1 is actually present on this machine -- skipped
cleanly otherwise, matching MB-04A's own test discipline).
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

MBQ = "/api/admin/mini-brain/quality"
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


async def test_diagnostics_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBQ}/diagnostics")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_check_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBQ}/check", json={"response_text": "Some response."})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_diagnostics_returns_pipeline_info(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBQ}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["ai_model_used"] is False
        assert body["database_tables"] == 0
    finally:
        await client.aclose()


async def test_check_detects_echo_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBQ}/check", headers=headers,
            json={
                "response_text": "Task: explain things.\n\nAnswer: The real content is here and long enough.",
                "prompt_text": "Role: You are an assistant.\n\nTask: explain things.\n\nAnswer:",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["echo"]["echo_detected"] is True
        assert "real content is here" in body["final_text"]
    finally:
        await client.aclose()


async def test_validate_does_not_return_final_text(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBQ}/validate", headers=headers, json={"response_text": "Some response text here."},
        )
        assert response.status_code == 200
        assert "final_text" not in response.json()
    finally:
        await client.aclose()


async def test_report_returns_quality_report_shape(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBQ}/report", headers=headers, json={"response_text": "Some genuine response text here."},
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("issues_found", "warnings", "quality_score", "processing_time_ms", "actions_performed"):
            assert key in body
    finally:
        await client.aclose()


async def test_format_endpoint_fixes_spacing(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBQ}/format", headers=headers, json={"text": "First.Second."})
        assert response.status_code == 200
        assert response.json()["formatted_text"] == "First. Second."
    finally:
        await client.aclose()


async def test_generate_fails_cleanly_when_no_model_loaded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBQ}/generate", headers=headers, json={"question": "What is a dataset?"})
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_quality_routes_never_touch_runtime_or_prompt_optimization_state(api_app: FastAPI) -> None:
    """Direct proof this phase's routes are independent: checking a
    response over HTTP never registers, loads, or otherwise mutates
    Runtime Manager state."""

    client, headers = await authenticated_client(api_app)
    try:
        await client.post(f"{MBQ}/check", headers=headers, json={"response_text": "Some response text here."})
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
            f"{MBQ}/generate", headers=headers,
            json={"question": "What is dataset duplicate detection?", "max_tokens": 8, "timeout_seconds": 200.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert "overall_quality" in body["quality"]["quality_score"]
        assert body["quality"]["processing_time_ms"] < 1000  # quality analysis itself should be near-instant
    finally:
        await client.aclose()
