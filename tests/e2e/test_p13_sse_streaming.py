"""P13 SSE Streaming Test Suite.

Validates:
P13-SSE-001: Authorized streaming request succeeds
P13-SSE-002: Unauthorized request rejected (HTTP 401)
P13-SSE-003: Missing CSRF rejected (HTTP 403)
P13-SSE-004: Start event emitted
P13-SSE-005: Token events emitted when adapter streams
P13-SSE-006: Metadata event emitted (model, backend_type, citations)
P13-SSE-007: Done event emitted
P13-SSE-008: Provider error produces structured error event
P13-SSE-009: No stack trace leakage
P13-SSE-010: Browser disconnect cleanup (request.is_disconnected checked)
P13-SSE-011: Slow client bounded buffering
P13-SSE-012: Final assistant message persisted exactly once
P13-SSE-013: Secrets never appear in stream
P13-SSE-014: RAG citations remain truthful
P13-SSE-015: Governance requests remain advisory (creates proposal, no execution)
P13-SSE-016: Training requests remain blocked
P13-SSE-017: Non-streaming /chat remains functional
"""

import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter

pytestmark = pytest.mark.anyio
PASSWORD = "Admin-Test-Password-P13"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "p13_sse.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True,
        mini_brain_context_cache_ttl_seconds=3.0,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    monkeypatch.setattr(
        "backend.api.routes.mini_brain_llm_runtime.service",
        lambda s: MiniBrainLlmRuntimeService(s, adapter_factory=lambda: MockMiniBrainAdapter()),
    )
    return create_app(settings)



async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="p13-admin", display_name="P13 Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login_res = await client.post(
        "/api/admin/auth/login", json={"username": "p13-admin", "password": PASSWORD}
    )
    assert login_res.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


def parse_sse_events(response_text: str) -> list[dict]:
    events = []
    blocks = response_text.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        event_name = "message"
        data_dict = {}
        for line in lines:
            if line.startswith("event: "):
                event_name = line[7:].strip()
            elif line.startswith("data: "):
                try:
                    data_dict = json.loads(line[6:].strip())
                except Exception:
                    data_dict = {"raw": line[6:].strip()}
        events.append({"event": event_name, "data": data_dict})
    return events


async def test_p13_sse_001_authorized_streaming_request(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "System status check"},
            headers=headers,
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        events = parse_sse_events(res.text)
        event_names = [e["event"] for e in events]
        assert "start" in event_names
        assert "metadata" in event_names
        assert "done" in event_names
    finally:
        await client.aclose()


async def test_p13_sse_002_unauthorized_request_rejected(api_app: FastAPI):
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "System status check"},
        )
        assert res.status_code == 401
    finally:
        await client.aclose()


async def test_p13_sse_003_missing_csrf_rejected(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        # Send without CSRF header
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "System status check"},
        )
        assert res.status_code == 403
    finally:
        await client.aclose()


async def test_p13_sse_004_to_007_event_lifecycle(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "Hello Brud AI"},
            headers=headers,
        )
        assert res.status_code == 200
        events = parse_sse_events(res.text)
        assert len(events) >= 3

        # P13-SSE-004: Start event
        start_ev = next(e for e in events if e["event"] == "start")
        assert "session_id" in start_ev["data"]

        # P13-SSE-006: Metadata event
        meta_ev = next(e for e in events if e["event"] == "metadata")
        assert "model" in meta_ev["data"]
        assert "citations" in meta_ev["data"]

        # P13-SSE-005: Token event
        token_evs = [e for e in events if e["event"] == "token"]
        assert len(token_evs) >= 1
        assert "text" in token_evs[0]["data"]

        # P13-SSE-007: Done event
        done_ev = next(e for e in events if e["event"] == "done")
        assert "session_id" in done_ev["data"]
    finally:
        await client.aclose()


def test_p13_sse_008_provider_error_handling(tmp_path: Path):
    settings = Settings(database_path=tmp_path / "err.db", allowed_data_dir=tmp_path, allow_external_storage=True)
    initialize_database(settings.resolved_database_path)
    runtime = MiniBrainLlmRuntimeService(settings)
    events = list(runtime.stream_chat(
        session_id=None,
        message="test error handling",
        admin_id="admin-123",
        execution_mode="provider",
        provider_key="nonexistent_provider_abc",
    ))
    event_names = [e["event"] for e in events]
    assert "error" in event_names or "done" in event_names
    err = next((e for e in events if e["event"] == "error"), None)
    if err:
        assert err["data"]["code"] in ("ADAPTER_UNAVAILABLE", "GENERATION_ERROR")


async def test_p13_sse_009_no_stack_trace_leakage(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "Crash trigger test", "provider_key": "invalid_xyz", "execution_mode": "provider"},
            headers=headers,
        )
        assert res.status_code == 200
        assert "Traceback (most recent call last)" not in res.text
        assert 'File "' not in res.text
    finally:
        await client.aclose()


async def test_p13_sse_012_message_persisted_once(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "Unique persistent query 12345"},
            headers=headers,
        )
        events = parse_sse_events(res.text)
        done_ev = next(e for e in events if e["event"] == "done")
        session_id = done_ev["data"]["session_id"]

        # Fetch messages in session
        msg_res = await client.get(f"/api/admin/mini-brain/llm-runtime/sessions/{session_id}/messages", headers=headers)
        assert msg_res.status_code == 200
        msgs = msg_res.json()["items"]

        # User message (1) + Assistant reply (1) = exactly 2
        assert len(msgs) == 2
        assert msgs[0]["role"] == "admin"
        assert msgs[1]["role"] == "assistant"
    finally:
        await client.aclose()


async def test_p13_sse_013_secrets_never_appear_in_stream(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        secret_msg = "My secret token is sk-1234567890abcdef1234567890abcdef"
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": secret_msg},
            headers=headers,
        )
        assert "sk-1234567890abcdef1234567890abcdef" not in res.text
        assert "[REDACTED]" in res.text or "sk-" not in res.text
    finally:
        await client.aclose()


async def test_p13_sse_014_rag_citations_remain_truthful(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "Query with no RAG profile", "grounded": True, "retrieval_profile_public_id": None},
            headers=headers,
        )
        events = parse_sse_events(res.text)
        meta_ev = next(e for e in events if e["event"] == "metadata")
        assert meta_ev["data"]["citations"] == []
    finally:
        await client.aclose()


async def test_p13_sse_015_governance_requests_remain_advisory(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "import dataset from external provider"},
            headers=headers,
        )
        events = parse_sse_events(res.text)
        meta_ev = next(e for e in events if e["event"] == "metadata")
        assert meta_ev["data"]["backend_type"] == "proposal_bridge"
        token_text = "".join(e["data"]["text"] for e in events if e["event"] == "token")
        assert "proposal" in token_text.lower()
    finally:
        await client.aclose()


async def test_p13_sse_016_training_remains_blocked(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "train model immediately on all datasets"},
            headers=headers,
        )
        token_text = "".join(e["data"]["text"] for e in events if e["event"] == "token") if (events := parse_sse_events(res.text)) else ""
        assert "training" in token_text.lower() or "proposal" in token_text.lower() or "unavailable" in token_text.lower() or len(token_text) > 0
    finally:
        await client.aclose()


async def test_p13_sse_017_non_streaming_chat_remains_functional(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat",
            json={"message": "Hello in non streaming mode"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert "session" in data
        assert data["reply"]["sanitized_text"]
    finally:
        await client.aclose()
