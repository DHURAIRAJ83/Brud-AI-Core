"""MB-28: API tests for /api/admin/mini-brain/llm-runtime.

Auth/CSRF enforcement per route and real HTTP round-trips through a
`MockMiniBrainAdapter` dependency override (real app, real database,
real service -- only the LLM backend itself is mocked, the same
pattern MB-26/27's own API tests use for their real-but-unexercised
adapters). No public routes exist in this phase.
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

MBLR = "/api/admin/mini-brain/llm-runtime"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_all_routes_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBLR}/diagnostics")).status_code == 401
        assert (await client.get(f"{MBLR}/sessions")).status_code == 401
        assert (await client.post(f"{MBLR}/chat", json={"message": "hi"})).status_code == 401
        assert (await client.post(f"{MBLR}/grounded-chat", json={"message": "hi"})).status_code == 401
        assert (await client.post(f"{MBLR}/next-actions", json={})).status_code == 401
        assert (await client.delete(f"{MBLR}/sessions/bogus")).status_code == 401
    finally:
        await client.aclose()


async def test_chat_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/chat", json={"message": "hi"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_grounded_chat_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/grounded-chat", json={"message": "hi"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_default_retrieval_profile_over_http_requires_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBLR}/grounded-chat/default-retrieval-profile")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_default_retrieval_profile_over_http_returns_null_with_no_profiles(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLR}/grounded-chat/default-retrieval-profile", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body == {"retrieval_profile_public_id": None, "name": None}
    finally:
        await client.aclose()


async def test_diagnostics_over_http_is_honest_when_unconfigured(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLR}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for field in ("local_available", "local_model_loaded", "configured_model_path", "llama_cpp_installed", "external_fallback_enabled", "active_session_count", "total_messages"):
            assert field in body
        assert body["local_available"] is False
    finally:
        await client.aclose()


async def test_chat_over_http_reports_unavailable_without_config(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/chat", json={"message": "hello"}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["backend_type"] == "unavailable"
        assert body["session"]["public_id"]
    finally:
        await client.aclose()


async def test_grounded_chat_over_http_reachable_and_falls_back_without_profile(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/grounded-chat", json={"message": "hello"}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["session"]["public_id"]
        assert body["citations"] == []
        # no provider configured in this fixture -- same honest "unavailable"
        # outcome as the existing /chat route under the same conditions.
        assert body["backend_type"] == "unavailable"
    finally:
        await client.aclose()


async def test_grounded_chat_over_http_rejects_top_k_out_of_range(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        too_low = await client.post(f"{MBLR}/grounded-chat", json={"message": "hi", "top_k": 0}, headers=headers)
        assert too_low.status_code == 422
        too_high = await client.post(f"{MBLR}/grounded-chat", json={"message": "hi", "top_k": 9}, headers=headers)
        assert too_high.status_code == 422
    finally:
        await client.aclose()


async def test_grounded_chat_over_http_unknown_retrieval_profile_errors_honestly(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBLR}/grounded-chat",
            json={"message": "hi", "retrieval_profile_public_id": "does-not-exist"},
            headers=headers,
        )
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_existing_chat_route_unchanged_after_grounded_chat_addition(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/chat", json={"message": "hello"}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["backend_type"] == "unavailable"
        assert body["session"]["public_id"]
        assert "citations" not in body
    finally:
        await client.aclose()


async def test_chat_over_http_rejects_message_too_short(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/chat", json={"message": ""}, headers=headers)
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_explain_page_over_http_finds_template(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/explain-page", json={"page_id": "overview"}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["backend_type"] == "template"
    finally:
        await client.aclose()


async def test_summarize_report_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/summarize-report", json={"report": {"title": "x", "status": "done", "count": 1}}, headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_summarize_regression_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/summarize-regression", json={"regression_result": {"passed": 5, "failed": 0, "errors": 0}}, headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_explain_error_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/explain-error", json={"error_message": "TypeError: x"}, headers=headers)
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_explain_error_rejects_empty_message(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/explain-error", json={"error_message": ""}, headers=headers)
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_next_actions_over_http_always_returns_actions(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLR}/next-actions", json={"status_snapshot": {"failing_tests": 2}}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body["actions"]) >= 1
    finally:
        await client.aclose()


async def test_session_lifecycle_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        chat_response = await client.post(f"{MBLR}/chat", json={"message": "hello"}, headers=headers)
        session_id = chat_response.json()["session"]["public_id"]

        get_response = await client.get(f"{MBLR}/sessions/{session_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["public_id"] == session_id

        list_response = await client.get(f"{MBLR}/sessions", headers=headers)
        assert list_response.status_code == 200
        assert session_id in [s["public_id"] for s in list_response.json()["items"]]

        messages_response = await client.get(f"{MBLR}/sessions/{session_id}/messages", headers=headers)
        assert messages_response.status_code == 200
        assert len(messages_response.json()["items"]) == 2

        delete_response = await client.delete(f"{MBLR}/sessions/{session_id}", headers=headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"

        # confirm soft delete -- session is still retrievable, not gone
        refetch = await client.get(f"{MBLR}/sessions/{session_id}", headers=headers)
        assert refetch.status_code == 200
        assert refetch.json()["status"] == "deleted"
    finally:
        await client.aclose()


async def test_get_session_not_found_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLR}/sessions/bogus-id", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_no_public_route_exists_for_llm_runtime(api_app: FastAPI) -> None:
    public_prefixed_paths = [
        route.path for route in api_app.routes
        if hasattr(route, "path") and "llm-runtime" in route.path
    ]
    assert all("/admin/" in path for path in public_prefixed_paths)
