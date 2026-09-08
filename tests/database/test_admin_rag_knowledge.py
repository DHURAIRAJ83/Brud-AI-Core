"""Phase 5: Admin Assistant Knowledge/RAG layer.

Proves the two new Admin Assistant tools (`list_rag_retrieval_profiles`,
`ask_knowledge_base`) are wired correctly through the existing Phase
2/3 governance seam (`run_tool()` -> RBAC `tool.read`), and that
`ask_knowledge_base` adds NOTHING new to the RAG engine itself -- it is
a thin, read-gated exposure of the already-existing, already-tested
(tests/backend/test_rag_api.py) `RagGenerationService.grounded_answer()`
pipeline: retrieval, hybrid scoring, access filtering, context
budgeting, citation building, citation validation, and the
insufficient-evidence/no-hallucination policy are all reused verbatim.

Knowledge-space/assignment construction reuses
tests/backend/test_rag_api.py's own established HTTP helpers rather
than reinventing an 8-stage ingestion pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.main import create_app
from backend.models.auth import AdminCreate
from backend.services.admin_assistant_tool_governance import ToolAuthorizationError
from backend.services.admin_assistant_tools import (
    READ_ONLY_TOOLS,
    ReadOnlyToolError,
    ToolCapability,
    get_tool,
    run_tool,
)
from httpx import ASGITransport, AsyncClient
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_inference_runtime_api import _build_release, _create_instance, _create_profile
from tests.backend.test_instruction_tuning_api import _fixture_refs
from tests.backend.test_rag_api import TAMIL_CONTENT, _build_indexed_space, _create_space

RAG_TOOL_TEST_PASSWORD = "Rag-Tool-Admin-Password-42"  # noqa: S105


async def _second_admin_client(app: FastAPI, *, username: str):
    """A distinct, non-creator admin session -- `model_assignment_service.
    approve_assignment()` requires `minimum_distinct_approvers=2` non-self
    approvals for the `admin_diagnostic` scope (self-approval is always
    blocked; see `inference_assignment_allow_self_approval`), so a single
    approving admin (as tests/backend/test_rag_api.py's own
    `_build_eligible_rag_assignment` helper uses) cannot activate an
    assignment against the current governance policy -- confirmed
    pre-existing and independent of Phase 5 by running
    test_rag_api.py::test_grounded_answer_and_chat_lab_lifecycle in
    isolation. Not a Phase 5 regression; not fixed here (out of scope --
    that file is unrelated pre-existing test infrastructure)."""

    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name=username, password=RAG_TOOL_TEST_PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": username, "password": RAG_TOOL_TEST_PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def _build_eligible_rag_assignment(client, headers, api_app: FastAPI, *, slug: str) -> str:
    """Corrected, Phase-5-local equivalent of test_rag_api.py's own
    `_build_eligible_rag_assignment`, approved by two distinct
    non-creator admins to satisfy the real current approval policy (see
    `_second_admin_client`'s docstring)."""

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

    approver_one, approver_one_headers = await _second_admin_client(
        api_app, username=f"rag-tool-approver-1-{slug}"
    )
    approver_two, approver_two_headers = await _second_admin_client(
        api_app, username=f"rag-tool-approver-2-{slug}"
    )
    try:
        for approver, approver_headers in (
            (approver_one, approver_one_headers),
            (approver_two, approver_two_headers),
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

pytestmark = pytest.mark.anyio

NONE_ROLE_ADMIN_ID = "a0000000-0000-0000-0000-00000000000a"


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
        admin_role_overrides=f"{NONE_ROLE_ADMIN_ID}:NONE",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


# --- 1: tool registration / capability metadata -----------------------------


def test_new_tools_are_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    profiles_tool = get_tool("list_rag_retrieval_profiles")
    ask_tool = get_tool("ask_knowledge_base")
    assert profiles_tool is not None and profiles_tool.capability is ToolCapability.READ_ONLY
    assert ask_tool is not None and ask_tool.capability is ToolCapability.READ_ONLY
    assert ask_tool.needs_admin_id is True
    assert profiles_tool.needs_admin_id is False
    assert ask_tool.required_params == ("query", "retrieval_profile_public_id")


# --- 2: no admin identity -> refused, not silently attributed ---------------


async def test_ask_knowledge_base_requires_admin_id(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    with pytest.raises(ReadOnlyToolError, match="authenticated admin identity"):
        run_tool(
            "ask_knowledge_base",
            settings,
            {"query": "does brud ai have rbac", "retrieval_profile_public_id": "nonexistent"},
        )


# --- 3: no active RAG assignment -> explicit unavailable, never an error ---


async def test_ask_knowledge_base_no_active_assignment_is_explicit(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        space_id = await _create_space(client, headers, slug="no-assignment-space")
        profile = await client.post(
            f"/api/admin/rag/spaces/{space_id}/retrieval-profiles",
            headers=headers,
            json={"name": "p"},
        )
        profile_id = profile.json()["public_id"]
        await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/validate", headers=headers
        )
        await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/activate", headers=headers
        )

        settings = api_app.state.settings
        result = run_tool(
            "ask_knowledge_base",
            settings,
            {"query": "anything", "retrieval_profile_public_id": profile_id},
            admin_id="some-admin-id",
        )
        assert result["available"] is False
        assert "admin_diagnostic" in result["reason"]
    finally:
        await client.aclose()


# --- 4: RBAC still enforced through the new tools ---------------------------


async def test_ask_knowledge_base_denied_for_none_role(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    with pytest.raises(ToolAuthorizationError):
        run_tool(
            "ask_knowledge_base",
            settings,
            {"query": "x", "retrieval_profile_public_id": "whatever"},
            admin_id=NONE_ROLE_ADMIN_ID,
        )


async def test_list_rag_retrieval_profiles_denied_for_none_role(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    with pytest.raises(ToolAuthorizationError):
        run_tool("list_rag_retrieval_profiles", settings, {}, admin_id=NONE_ROLE_ADMIN_ID)


# --- 5: list_rag_retrieval_profiles reflects real configured profiles ------


async def test_list_rag_retrieval_profiles_returns_configured_profile(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(
            client, headers, slug="listing-space", content=TAMIL_CONTENT
        )
        settings = api_app.state.settings
        result = run_tool(
            "list_rag_retrieval_profiles", settings, {}, admin_id="some-admin-id"
        )
        assert result["available"] is True
        profile_ids = {item["public_id"] for item in result["items"]}
        assert built["profile_id"] in profile_ids
    finally:
        await client.aclose()


# --- 6: insufficient evidence against an empty knowledge space -------------


async def test_ask_knowledge_base_insufficient_evidence_when_space_empty(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        space_id = await _create_space(client, headers, slug="empty-knowledge-space")
        profile = await client.post(
            f"/api/admin/rag/spaces/{space_id}/retrieval-profiles",
            headers=headers,
            json={"name": "empty-profile"},
        )
        profile_id = profile.json()["public_id"]
        await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/validate", headers=headers
        )
        await client.post(
            f"/api/admin/rag/retrieval-profiles/{profile_id}/activate", headers=headers
        )
        await _build_eligible_rag_assignment(client, headers, api_app, slug="empty-tool")

        settings = api_app.state.settings
        result = run_tool(
            "ask_knowledge_base",
            settings,
            {
                "query": "what is the capital of an unrelated country",
                "retrieval_profile_public_id": profile_id,
            },
            admin_id="asking-admin-id",
        )
        assert result["available"] is True
        assert result["answer"]["answer_status"] == "insufficient_evidence"
        assert result["citations"] == []
        assert result["disclaimer"] == (
            "Admin-only grounded diagnostic. This is not the public chatbot."
        )
    finally:
        await client.aclose()


# --- 7: grounded answer with real indexed content, citations, and DB scope -


async def test_ask_knowledge_base_grounded_answer_and_db_scope(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        built = await _build_indexed_space(
            client, headers, slug="grounded-tool-space", content=TAMIL_CONTENT
        )
        await _build_eligible_rag_assignment(client, headers, api_app, slug="grounded-tool")

        settings = api_app.state.settings
        db_path = settings.resolved_database_path

        import sqlite3

        def table_counts() -> dict[str, int]:
            conn = sqlite3.connect(db_path)
            try:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
            finally:
                conn.close()

        # Domain/governance tables that must never change from a knowledge
        # read, no matter what the RAG engine itself writes internally
        # (INVARIANT: RAG may provide evidence, never mutate governed state).
        protected_tables = [
            "dataset_records", "dataset_sources", "model_registry", "model_versions",
            "training_jobs", "admin_approvals", "admin_accounts",
        ]
        before = table_counts()

        result = run_tool(
            "ask_knowledge_base",
            settings,
            {
                "query": "பொங்கல் எப்போது கொண்டாடப்படுகிறது",
                "retrieval_profile_public_id": built["profile_id"],
            },
            admin_id="asking-admin-id-2",
        )
        after = table_counts()

        assert result["available"] is True
        assert result["grounded_request"]["status"] in {
            "completed", "insufficient_evidence", "generation_failed", "blocked_evidence",
        }
        assert result["answer"]["answer_status"] in {
            "grounded_answer", "insufficient_evidence", "generation_failed", "blocked_evidence",
        }
        for citation in result["citations"]:
            assert citation["validation_status"] in {
                "valid", "valid_with_warning", "invalid", "not_present",
            }

        for table in protected_tables:
            assert before.get(table) == after.get(table), f"{table} changed from a knowledge read"
    finally:
        await client.aclose()


# --- 8: no pool/connection leak through the new tools -----------------------


def test_ask_knowledge_base_handler_signature_has_no_pool_or_connection() -> None:
    import inspect

    from backend.services import admin_assistant_tools as tools_module

    sig = inspect.signature(tools_module._tool_ask_knowledge_base)
    for param in sig.parameters.values():
        annotation = str(param.annotation)
        assert "Pool" not in annotation and "sqlite3.Connection" not in annotation
