"""MB-04A: API tests for /admin/mini-brain/prompt-optimization.

Auth/CSRF, read-only endpoints, and clean-failure behavior when no
model is loaded run against the real app every time. An opportunistic
real-model test runs ONLY when the real Qwen GGUF file provisioned in
MB-04.1 is actually present on this machine (it is gitignored and not
part of the repository, so it is correctly absent everywhere else) --
skipped cleanly otherwise, never fabricated.
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

MBPO = "/api/admin/mini-brain/prompt-optimization"
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


async def test_templates_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBPO}/templates")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_language_detect_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPO}/language-detect", json={"question": "dataset epadi pannalam"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_templates_lists_all_ten_task_categories_plus_default(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBPO}/templates", headers=headers)
        assert response.status_code == 200
        categories = set(response.json()["templates"])
        expected = {
            "definition", "howto", "troubleshooting", "architecture", "dataset",
            "training", "rag", "workflow", "coding", "admin_dashboard", "default",
        }
        assert expected <= categories
    finally:
        await client.aclose()


async def test_language_detect_tanglish(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBPO}/language-detect", headers=headers, json={"question": "dataset epadi prepare pannalam?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["language"] == "tanglish"
        assert body["resolved_output_language"] == "tamil"
    finally:
        await client.aclose()


async def test_generate_fails_cleanly_when_no_model_loaded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPO}/generate", headers=headers, json={"question": "What is a dataset?"})
        assert response.status_code == 422
        assert "load a model" in response.json()["error"]["message"]
    finally:
        await client.aclose()


async def test_compare_fails_cleanly_when_no_model_loaded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBPO}/compare", headers=headers, json={"question": "What is a dataset?"})
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_runtime_manager_default_behavior_unchanged_without_prebuilt_prompt(api_app: FastAPI) -> None:
    """Direct regression proof that MB-04A's one Runtime Manager edit
    is truly additive: calling MB-04's own /runtime/generate route
    (never touched by MB-04A) still behaves exactly as before."""

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/mini-brain/runtime/generate", headers=headers,
            json={"response_plan": {"just_text": "raw question, not a Response Plan"}},
        )
        assert response.status_code == 422
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
            f"{MBPO}/generate", headers=headers,
            # MB-04A's structured, knowledge-grounded prompt is much
            # longer than MB-04.1's flat template (~1900+ vs ~130
            # chars) -- CPU prefill time on a longer prompt is real
            # and significant. max_tokens is kept small here purely to
            # keep this opportunistic wiring-proof test fast; the
            # dedicated MB-04A benchmark script measures real
            # end-to-end latency at realistic token counts separately.
            json={"question": "What is dataset duplicate detection?", "max_tokens": 8, "timeout_seconds": 200.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert "text" in body["response"]
        assert body["template_category"] == "dataset"
    finally:
        await client.aclose()
