"""Phase 6, Part A/B: reproduces and fixes the pre-existing bug Phase 5
discovered in `AdminAssistantChatService._resolve_admin_diagnostic_assignment()`.

Root cause (confirmed by direct inspection of
`backend/database/repositories/inference_runtime.py`):
`list_assignments()` is a plain `SELECT * FROM inference_model_assignments`
-- it has no `scope_key` column. That column only exists on the
separate, joined single-row `.assignment()` lookup (via
`inference_assignment_scopes`). The pre-fix code read
`row["scope_key"]` directly off a `list_assignments()` row, which
raises `IndexError` (sqlite3.Row's missing-key error) the instant any
assignment row exists -- masked pre-Phase-6 only because no existing
test ever created a real assignment before exercising
`llm_status()`/`_generate_llm_reply()`.

Severity, confirmed here: neither `_generate_llm_reply()` nor its
`send_message()` call site wraps `_resolve_admin_diagnostic_assignment()`
in a try/except -- the pre-fix `IndexError` would propagate uncaught
out of `send_message()` (an unhandled 500, not a graceful
"AI response generation unavailable" fallback). This is a stricter
characterization than Phase 5's initial "fails closed to unavailable
message" note.

Uses tests/backend/test_rag_api.py's + Phase 5's own corrected
(2-distinct-non-self-approver) assignment-building pattern -- entirely
isolated temporary databases, never the production database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.main import create_app
from backend.models.auth import AdminCreate
from backend.services.admin_assistant_chat_service import (
    ADMIN_ASSISTANT_LLM_SCOPE,
    AdminAssistantChatService,
)
from httpx import ASGITransport, AsyncClient
from tests.backend.test_inference_runtime_api import _build_release, _create_instance, _create_profile
from tests.backend.test_instruction_tuning_api import _fixture_refs

pytestmark = pytest.mark.anyio

PASSWORD = "Assignment-Resolution-Password-42"  # noqa: S105


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


async def _authenticated_client_as(app: FastAPI, username: str):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name=username, password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def _build_active_admin_diagnostic_assignment(
    client, headers, api_app: FastAPI, *, slug: str
) -> str:
    """2 distinct non-creator approvers -- see
    tests/database/test_admin_rag_knowledge.py's `_second_admin_client`
    docstring for why a single self-approval (the pattern
    tests/backend/test_rag_api.py's own helper uses) cannot activate an
    assignment against the current approval policy. Not fixed here
    (pre-existing, unrelated to Phase 6's assignment-resolution bug)."""

    refs = _fixture_refs(api_app)
    release_id, _family_id, _run_id = await _build_release(
        client, headers, api_app, refs,
        label="test_only_runtime_fixture", notes="not_chat_capable", slug=slug,
    )
    profile_id = await _create_profile(client, headers)
    instance_id = await _create_instance(client, headers, profile_id)
    loaded = await client.post(
        f"/api/admin/inference-runtime/instances/{instance_id}/load",
        headers=headers,
        json={"release_public_id": release_id},
    )
    assert loaded.status_code == 200, loaded.text

    assignment = await client.post(
        "/api/admin/inference-runtime/assignments",
        headers=headers,
        json={
            "scope": "admin_diagnostic",
            "release_public_id": release_id,
            "runtime_profile_public_id": profile_id,
        },
    )
    assert assignment.status_code == 200, assignment.text
    assignment_id = assignment.json()["public_id"]
    await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
    )

    approver_one, approver_one_headers = await _authenticated_client_as(
        api_app, f"assign-approver-1-{slug}"
    )
    approver_two, approver_two_headers = await _authenticated_client_as(
        api_app, f"assign-approver-2-{slug}"
    )
    try:
        for approver, approver_headers in (
            (approver_one, approver_one_headers), (approver_two, approver_two_headers),
        ):
            approved = await approver.post(
                f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
                headers=approver_headers,
                json={"role": "release", "decision": "approve", "comment": "ok"},
            )
            assert approved.status_code == 200, approved.text
    finally:
        await approver_one.aclose()
        await approver_two.aclose()

    activated = await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
        headers=headers,
        json={},
    )
    assert activated.status_code == 200, activated.text
    return assignment_id


# --- Part A: isolated reproduction of the root cause ------------------------


async def test_a_reproduction_list_assignments_row_has_no_scope_key(api_app: FastAPI) -> None:
    """Direct, isolated proof of the root cause: a real active
    admin_diagnostic assignment's `list_assignments()` row cannot be
    indexed by `scope_key` -- this is exactly the access the pre-fix
    code performed."""

    client, headers = await _authenticated_client_as(api_app, "repro-admin")
    try:
        await _build_active_admin_diagnostic_assignment(client, headers, api_app, slug="repro")
        settings = api_app.state.settings
        repository = InferenceRuntimeRepository(settings.resolved_database_path)
        with repository.transaction() as connection:
            rows = repository.list_assignments(connection)
        assert len(rows) >= 1
        with pytest.raises(IndexError):
            _ = rows[0]["scope_key"]  # the exact pre-fix access pattern
        # The real column the fixed code uses instead is present:
        assert rows[0]["model_assignment_scope_id"] is not None
    finally:
        await client.aclose()


# --- Part B.1: no admin_diagnostic assignment configured --------------------


async def test_b1_no_assignment_resolves_to_none(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    service = AdminAssistantChatService(settings)
    assert service._resolve_admin_diagnostic_assignment() is None
    status = service.llm_status()
    assert status["llm_available"] is False
    assert status["assignment_public_id"] is None


# --- B.2: a valid, active admin_diagnostic assignment ------------------------


async def test_b2_valid_admin_diagnostic_assignment_resolves_without_crashing(
    api_app: FastAPI,
) -> None:
    client, headers = await _authenticated_client_as(api_app, "valid-admin")
    try:
        assignment_id = await _build_active_admin_diagnostic_assignment(
            client, headers, api_app, slug="valid"
        )
        settings = api_app.state.settings
        service = AdminAssistantChatService(settings)

        resolved = service._resolve_admin_diagnostic_assignment()
        assert resolved is not None
        assert resolved["public_id"] == assignment_id
        assert resolved["status"] == "active"

        status = service.llm_status()
        assert status["llm_available"] is True
        assert status["assignment_public_id"] == assignment_id
    finally:
        await client.aclose()


# --- B.3: an assignment that exists but is for an unrelated scope -----------


async def test_b3_unrelated_scope_assignment_is_ignored(api_app: FastAPI) -> None:
    client, headers = await _authenticated_client_as(api_app, "unrelated-admin")
    try:
        refs = _fixture_refs(api_app)
        release_id, _family_id, _run_id = await _build_release(
            client, headers, api_app, refs,
            label="test_only_runtime_fixture", notes="not_chat_capable", slug="unrelated",
        )
        profile_id = await _create_profile(client, headers)
        instance_id = await _create_instance(client, headers, profile_id)
        await client.post(
            f"/api/admin/inference-runtime/instances/{instance_id}/load",
            headers=headers,
            json={"release_public_id": release_id},
        )
        # internal_canary, not admin_diagnostic -- must never be picked up.
        assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "internal_canary",
                "release_public_id": release_id,
                "runtime_profile_public_id": profile_id,
            },
        )
        assert assignment.status_code == 200, assignment.text

        settings = api_app.state.settings
        service = AdminAssistantChatService(settings)
        assert service._resolve_admin_diagnostic_assignment() is None
        assert service.llm_status()["llm_available"] is False
    finally:
        await client.aclose()


# --- B.4: assignment-scope row itself missing (edge case, must not crash) --


def test_b4_missing_scope_definition_resolves_gracefully(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "no-scope.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    repository = InferenceRuntimeRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        connection.execute(
            "DELETE FROM inference_assignment_scopes WHERE scope_key=?",
            (ADMIN_ASSISTANT_LLM_SCOPE,),
        )
        with pytest.raises(NotFoundError):
            repository.scope_by_key(connection, ADMIN_ASSISTANT_LLM_SCOPE)

    service = AdminAssistantChatService(settings)
    assert service._resolve_admin_diagnostic_assignment() is None
    assert service.llm_status()["llm_available"] is False


# --- B.5/B.6: correct failure/success behavior end to end via send_message -


async def test_b5_b6_open_ended_chat_no_longer_crashes_with_a_real_assignment(
    api_app: FastAPI,
) -> None:
    """The actual regression: with a real active admin_diagnostic
    assignment present, `send_message()`'s open-ended path must not
    raise -- it must either produce a real LLM reply or the
    deterministic GENERATION_UNAVAILABLE_MESSAGE fallback, never an
    unhandled exception."""

    client, headers = await _authenticated_client_as(api_app, "chat-admin")
    try:
        await _build_active_admin_diagnostic_assignment(client, headers, api_app, slug="chat")
        response = await client.post(
            "/api/admin/assistant/chat",
            headers=headers,
            json={
                "message": "what does this dashboard help me do today",
                "page_id": "overview",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["answer"], str) and body["answer"]
    finally:
        await client.aclose()
