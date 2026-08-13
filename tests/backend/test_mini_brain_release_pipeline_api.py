"""MB-07: API tests for /admin/mini-brain/release-pipeline.

Auth/CSRF requirements and route wiring over real HTTP. The full
12-stage real pipeline (real GGUF export, real llama_cpp load, real
Model Release governance composition) is already proven at the service
layer in test_mini_brain_release_pipeline_service.py -- this file
confirms the routes correctly translate HTTP requests into those same
service calls, not a second full run of the expensive real pipeline.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.auth import AdminCreate
from backend.models.model_release import ModelReleaseFamilyCreate
from backend.services.model_release_service import ModelReleaseService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_instruction_tuning_api import _fixture_refs

pytestmark = pytest.mark.anyio

MBRP = "/api/admin/mini-brain/release-pipeline"
CHECKPOINT_PUBLIC_ID = "50000000-0000-0000-0000-000000000500"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports", document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports", core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts", release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBRP}/sessions")).status_code == 401
        assert (await client.get(f"{MBRP}/diagnostics")).status_code == 401
    finally:
        await client.aclose()


async def test_diagnostics_lists_only_genuinely_supported_levels(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRP}/diagnostics", headers=headers)
        assert response.status_code == 200
        levels = response.json()["quantization_levels_supported"]
        assert "q8_0" in levels
        assert "q4_k_m" not in levels
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBRP}/sessions", json={"core_model_version_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_create_and_fetch_session_over_http(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    admin = AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="mb07-http-admin", display_name="A", password="password12345")
    )
    model_release = ModelReleaseService(
        ModelReleaseRepository(api_app.state.settings.resolved_database_path), api_app.state.settings
    )
    family = model_release.create_family(
        ModelReleaseFamilyCreate(name="HTTP Family", slug="http-family"), admin.public_id,
    )

    client, headers = await authenticated_client(api_app)
    try:
        create_response = await client.post(
            f"{MBRP}/sessions", headers=headers,
            json={
                "core_model_version_public_id": refs["base_model"],
                "pretraining_checkpoint_public_id": CHECKPOINT_PUBLIC_ID,
                "model_release_family_public_id": family["public_id"],
                "target_quantizations": ["f16"],
            },
        )
        assert create_response.status_code == 200, create_response.text
        session = create_response.json()
        assert session["stage"] == "checkpoint_validation"
        session_id = session["public_id"]

        get_response = await client.get(f"{MBRP}/sessions/{session_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["public_id"] == session_id

        list_response = await client.get(f"{MBRP}/sessions", headers=headers)
        assert any(s["public_id"] == session_id for s in list_response.json()["items"])

        validate_response = await client.post(f"{MBRP}/sessions/{session_id}/validate", headers=headers)
        assert validate_response.status_code == 200, validate_response.text
        assert validate_response.json()["stage"] == "conversion"

        events_response = await client.get(f"{MBRP}/sessions/{session_id}/events", headers=headers)
        event_types = [e["event_type"] for e in events_response.json()["items"]]
        assert "checkpoint_validated" in event_types

        # wrong-stage guard surfaces as 422 at the HTTP layer too
        wrong_stage = await client.post(f"{MBRP}/sessions/{session_id}/validate", headers=headers)
        assert wrong_stage.status_code == 422
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBRP}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()
