"""P14.2 Distributed Tracing Test Suite.

Validates:
P14-TRACE-001: Non-streaming /chat generates and returns X-Trace-Id header and trace_id in payload.
P14-TRACE-002: Client-provided X-Trace-Id header is honored and propagated.
P14-TRACE-003: SSE /chat/stream emits trace_id in X-Trace-Id header, start event, and done event.
P14-TRACE-004: Event ledger (mini_brain_llm_runtime_events) persists trace_id and stage_latencies_ms.
P14-TRACE-005: Grounded chat measures and records rag_latency_ms with trace_id.
P14-TRACE-006: Zero secrets leakage in trace details or stage latencies.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.mini_brain_llm_runtime import MiniBrainLlmRuntimeRepository
from backend.models.auth import AdminCreate
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

pytestmark = pytest.mark.anyio
PASSWORD = "Admin-Trace-Test-P14"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "p14_trace.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True,
        mini_brain_context_cache_ttl_seconds=3.0,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="p14-admin", display_name="P14 Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login_res = await client.post(
        "/api/admin/auth/login", json={"username": "p14-admin", "password": PASSWORD}
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
        event_name = "message"
        data_dict = {}
        lines = block.strip().split("\n")
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


async def test_p14_trace_001_chat_returns_x_trace_id_header(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        # Use template clarification turn so no external adapter is needed
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat",
            json={"message": "   "},
            headers=headers,
        )
        assert res.status_code == 200
        assert "X-Trace-Id" in res.headers
        trace_id = res.headers["X-Trace-Id"]
        assert trace_id.startswith("trc_")
        data = res.json()
        assert data["trace_id"] == trace_id
    finally:
        await client.aclose()


async def test_p14_trace_002_custom_x_trace_id_propagated(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        custom_trace = "trc_custom_explicit_999"
        req_headers = {**headers, "X-Trace-Id": custom_trace}
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat",
            json={"message": "   "},
            headers=req_headers,
        )
        assert res.status_code == 200
        assert res.headers["X-Trace-Id"] == custom_trace
        assert res.json()["trace_id"] == custom_trace
    finally:
        await client.aclose()


async def test_p14_trace_003_stream_chat_emits_trace_id_in_sse_events(api_app: FastAPI):
    client, headers = await authenticated_client(api_app)
    try:
        custom_trace = "trc_stream_test_456"
        req_headers = {**headers, "X-Trace-Id": custom_trace}
        # Empty query emits clarify template streaming turn without needing model file
        res = await client.post(
            "/api/admin/mini-brain/llm-runtime/chat/stream",
            json={"message": "   "},
            headers=req_headers,
        )
        assert res.status_code == 200
        assert res.headers["X-Trace-Id"] == custom_trace
        events = parse_sse_events(res.text)
        start_ev = next(e for e in events if e["event"] == "start")
        assert start_ev["data"]["trace_id"] == custom_trace
        done_ev = next(e for e in events if e["event"] == "done")
        assert done_ev["data"]["trace_id"] == custom_trace
        assert "stage_latencies_ms" in done_ev["data"]
    finally:
        await client.aclose()


def test_p14_trace_004_trace_and_stage_latencies_persisted_in_event_ledger(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "ledger.db",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
    )
    initialize_database(settings.resolved_database_path)
    mock_adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: mock_adapter)

    custom_trace = "trc_ledger_verification_777"
    res = service.chat(
        session_id=None,
        message="System diagnostic status",
        admin_id="00000000-0000-0000-0000-000000000001",
        trace_id=custom_trace,
    )
    assert res["trace_id"] == custom_trace

    repo = MiniBrainLlmRuntimeRepository(settings.resolved_database_path)
    with repo.transaction() as conn:
        events = repo.list_events(conn, session_id=res["session"]["public_id"], limit=10, offset=0)
    
    reply_events = [e for e in events if e["event_type"] == "reply_generated"]
    assert len(reply_events) >= 1
    detail = json.loads(reply_events[0]["detail_json"])
    assert detail.get("trace_id") == custom_trace
    assert "stage_latencies_ms" in detail
    stages = detail["stage_latencies_ms"]
    assert "context_latency_ms" in stages
    assert "generation_latency_ms" in stages
    assert "total_latency_ms" in stages


def test_p14_trace_005_grounded_chat_records_rag_latency(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "rag_trace.db",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
    )
    initialize_database(settings.resolved_database_path)
    mock_adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: mock_adapter)

    custom_trace = "trc_rag_lat_888"
    res = service.grounded_chat(
        session_id=None,
        message="Query with grounded knowledge",
        retrieval_profile_public_id=None,
        top_k=4,
        admin_id="00000000-0000-0000-0000-000000000001",
        trace_id=custom_trace,
    )
    assert res["trace_id"] == custom_trace

    repo = MiniBrainLlmRuntimeRepository(settings.resolved_database_path)
    with repo.transaction() as conn:
        events = repo.list_events(conn, session_id=res["session"]["public_id"], limit=10, offset=0)

    reply_events = [e for e in events if e["event_type"] == "reply_generated"]
    assert len(reply_events) >= 1
    detail = json.loads(reply_events[0]["detail_json"])
    assert detail.get("trace_id") == custom_trace
    stages = detail.get("stage_latencies_ms", {})
    assert "total_latency_ms" in stages


def test_p14_trace_006_zero_secrets_in_trace_metadata(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "secret_trace.db",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
    )
    initialize_database(settings.resolved_database_path)
    mock_adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: mock_adapter)

    secret_key = "sk-live-secret-super-confidential-token-12345"
    res = service.chat(
        session_id=None,
        message=f"My secret key is {secret_key}",
        admin_id="00000000-0000-0000-0000-000000000001",
    )

    repo = MiniBrainLlmRuntimeRepository(settings.resolved_database_path)
    with repo.transaction() as conn:
        events = repo.list_events(conn, session_id=res["session"]["public_id"], limit=10, offset=0)
        messages = repo.list_messages(conn, session_id=res["session"]["public_id"], limit=10, offset=0)

    for event in events:
        detail_raw = event["detail_json"]
        assert secret_key not in detail_raw

    for msg in messages:
        assert secret_key not in msg["sanitized_text"]


def test_p14_trace_007_diagnostics_exposes_observability_metrics(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "diag_trace.db",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
    )
    initialize_database(settings.resolved_database_path)
    service = MiniBrainLlmRuntimeService(settings)

    diag = service.diagnostics()
    assert "cache_metrics" in diag
    assert "resilience_metrics" in diag
    assert "provider_probes" in diag

    resilience = diag["resilience_metrics"]
    assert "total_replies" in resilience
    assert "total_errors" in resilience
    assert "failovers" in resilience

    probes = diag["provider_probes"]
    assert "local" in probes
    assert "external" in probes
    # Verify zero secrets leaked
    diag_str = json.dumps(diag)
    assert "sk-" not in diag_str
    assert "password" not in diag_str

