"""MB-43: Retrieval Profile Management UI backend coverage -- real HTTP
round trips against a real SQLite database (no mocks), reusing the same
`_build_indexed_space` end-to-end fixture (space -> source -> version ->
chunk-set -> embedding run -> vector index -> keyword index -> validated
+ activated retrieval profile) that test_rag_api.py already established.

Covers the three MB-43 task-5 requirements:
  1. only active profiles can become the default,
  2. changing the default updates the API response,
  3. deactivated profiles are removed from default selection.
Plus the two supporting list/detail surfaces (knowledge space name,
vector index status) that back the new Retrieval Profile Management UI.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_rag_api import TAMIL_CONTENT, _build_indexed_space

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


DEFAULT_PROFILE_URL = "/api/admin/mini-brain/llm-runtime/grounded-chat/default-retrieval-profile"


async def test_list_retrieval_profiles_includes_knowledge_space_name(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(client, headers, slug="mb43-list", content=TAMIL_CONTENT)

        listing = await client.get("/api/admin/rag/retrieval-profiles", headers=headers)
        assert listing.status_code == 200, listing.text
        items = listing.json()["items"]
        matched = next(item for item in items if item["public_id"] == built["profile_id"])
        assert matched["knowledge_space_name"] == "Space mb43-list"
        assert matched["knowledge_space_public_id"] == built["space_id"]
        assert matched["status"] == "active"
        # internal FK column must never leak, even though it drove the JOIN
        assert "knowledge_space_id" not in matched
    finally:
        await client.aclose()


async def test_latest_vector_index_for_space_endpoint(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(client, headers, slug="mb43-vec", content=TAMIL_CONTENT)

        response = await client.get(
            f"/api/admin/rag/spaces/{built['space_id']}/latest-vector-index", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body is not None
        assert body["status"] == "active"
    finally:
        await client.aclose()


async def test_latest_vector_index_for_space_with_no_index_returns_null(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        space = await client.post(
            "/api/admin/rag/spaces", headers=headers, json={"name": "Empty space", "slug": "mb43-empty"}
        )
        assert space.status_code == 200, space.text
        space_id = space.json()["public_id"]

        response = await client.get(
            f"/api/admin/rag/spaces/{space_id}/latest-vector-index", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json() is None
    finally:
        await client.aclose()


async def test_deactivate_profile_reverts_to_validated_and_is_reversible(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(client, headers, slug="mb43-deact", content=TAMIL_CONTENT)
        profile_id = built["profile_id"]

        deactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/deactivate", headers=headers
        )
        assert deactivated.status_code == 200, deactivated.text
        assert deactivated.json()["status"] == "validated"

        # deactivating an already-non-active profile is refused
        again = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/deactivate", headers=headers
        )
        assert again.status_code in (400, 422), again.text

        # re-activation works directly from "validated" -- no re-validate needed
        reactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/activate", headers=headers
        )
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["status"] == "active"
    finally:
        await client.aclose()


async def test_only_active_profile_can_become_default(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(client, headers, slug="mb43-gate", content=TAMIL_CONTENT)
        profile_id = built["profile_id"]

        # deactivate it (-> "validated"), then try to set it as default
        deactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/deactivate", headers=headers
        )
        assert deactivated.status_code == 200, deactivated.text

        rejected = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": profile_id}
        )
        assert rejected.status_code in (400, 422), rejected.text

        # re-activate, then setting it as default succeeds
        reactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/activate", headers=headers
        )
        assert reactivated.status_code == 200, reactivated.text

        accepted = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": profile_id}
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["retrieval_profile_public_id"] == profile_id
    finally:
        await client.aclose()


async def test_changing_default_updates_the_api_response(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built_a = await _build_indexed_space(client, headers, slug="mb43-default-a", content=TAMIL_CONTENT)
        built_b = await _build_indexed_space(client, headers, slug="mb43-default-b", content=TAMIL_CONTENT)

        set_a = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": built_a["profile_id"]}
        )
        assert set_a.status_code == 200, set_a.text

        get_after_a = await client.get(DEFAULT_PROFILE_URL, headers=headers)
        assert get_after_a.status_code == 200, get_after_a.text
        assert get_after_a.json()["retrieval_profile_public_id"] == built_a["profile_id"]

        set_b = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": built_b["profile_id"]}
        )
        assert set_b.status_code == 200, set_b.text

        get_after_b = await client.get(DEFAULT_PROFILE_URL, headers=headers)
        assert get_after_b.status_code == 200, get_after_b.text
        assert get_after_b.json()["retrieval_profile_public_id"] == built_b["profile_id"]
    finally:
        await client.aclose()


async def test_deactivated_default_profile_is_removed_from_default_selection(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        # only one active profile exists in this DB -- once it's set as
        # the default and then deactivated, default selection must fall
        # back to nulls, never keep returning the now-inactive profile.
        built = await _build_indexed_space(client, headers, slug="mb43-fallback", content=TAMIL_CONTENT)
        profile_id = built["profile_id"]

        set_default = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": profile_id}
        )
        assert set_default.status_code == 200, set_default.text
        assert set_default.json()["retrieval_profile_public_id"] == profile_id

        deactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/deactivate", headers=headers
        )
        assert deactivated.status_code == 200, deactivated.text

        get_after_deactivate = await client.get(DEFAULT_PROFILE_URL, headers=headers)
        assert get_after_deactivate.status_code == 200, get_after_deactivate.text
        body = get_after_deactivate.json()
        assert body["retrieval_profile_public_id"] is None
        assert body["name"] is None
    finally:
        await client.aclose()


async def test_deactivated_default_falls_back_to_another_active_profile(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built_a = await _build_indexed_space(client, headers, slug="mb43-fb-a", content=TAMIL_CONTENT)
        built_b = await _build_indexed_space(client, headers, slug="mb43-fb-b", content=TAMIL_CONTENT)

        set_default = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": built_a["profile_id"]}
        )
        assert set_default.status_code == 200, set_default.text

        deactivated = await client.post(
            f"/api/admin/rag/retrieval-profiles/{built_a['profile_id']}/deactivate", headers=headers
        )
        assert deactivated.status_code == 200, deactivated.text

        get_after_deactivate = await client.get(DEFAULT_PROFILE_URL, headers=headers)
        assert get_after_deactivate.status_code == 200, get_after_deactivate.text
        body = get_after_deactivate.json()
        # deactivated profile A must never be returned again; auto-detection
        # falls through to the other real active profile (B) instead.
        assert body["retrieval_profile_public_id"] == built_b["profile_id"]
    finally:
        await client.aclose()


async def test_set_default_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(client, headers=_headers, slug="mb43-csrf", content=TAMIL_CONTENT)
        response = await client.post(
            DEFAULT_PROFILE_URL, json={"retrieval_profile_public_id": built["profile_id"]}
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_set_default_with_unknown_profile_id_returns_not_found(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            DEFAULT_PROFILE_URL, headers=headers, json={"retrieval_profile_public_id": "does-not-exist"}
        )
        assert response.status_code == 404, response.text
    finally:
        await client.aclose()
