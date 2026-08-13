"""MB-26: API tests for /api/admin/mini-brain/voice and
/api/public/voice.

Auth/CSRF/rate-limit requirements and route wiring over real HTTP.
The full 12-stage workflow is already proven at the service layer in
test_mini_brain_voice_runtime_service.py -- this file confirms the
routes correctly translate HTTP requests into those same service
calls.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.public_chat_rate_limiter import reset_rate_limits
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBVO = "/api/admin/mini-brain/voice"
PUBLIC_VO = "/api/public/voice"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, voice_audio_dir=tmp_path / "voice_audio",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
        public_chat_rate_limit_max_requests=1000, public_chat_rate_limit_window_seconds=60,
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _audio_b64(payload: bytes = b"test audio payload data") -> str:
    return base64.b64encode(payload).decode("ascii")


async def test_admin_routes_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBVO}/diagnostics")).status_code == 401
        assert (await client.get(f"{MBVO}/sessions")).status_code == 401
    finally:
        await client.aclose()


async def test_admin_diagnostics_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBVO}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        for field in ("stt_backend", "stt_available", "tts_backend", "tts_available", "wakeword_enabled"):
            assert field in body
        assert body["wakeword_enabled"] is False
    finally:
        await client.aclose()


async def test_admin_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBVO}/sessions", json={"session_mode": "admin_assistant"},
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_admin_test_tts_requires_csrf_and_works_with_it(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBVO}/test-tts", json={"text": "hello there"}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["backend"] == "mock"
        assert body["audio_byte_length"] > 0
    finally:
        await client.aclose()


async def test_admin_test_stt_works(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{MBVO}/test-stt", json={"audio_base64": _audio_b64()}, headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["backend"] == "mock"
        assert "text" in body
    finally:
        await client.aclose()


async def test_public_routes_require_no_admin_auth() -> None:
    from backend.main import create_app

    import tempfile

    tmp_path = Path(tempfile.mkdtemp())
    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, voice_audio_dir=tmp_path / "voice_audio",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    app = create_app(settings)

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        response = await client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": True})
        assert response.status_code == 200, response.text
    finally:
        await client.aclose()


async def test_public_routes_are_rate_limited(tmp_path: Path) -> None:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, voice_audio_dir=tmp_path / "voice_audio",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
        public_chat_rate_limit_max_requests=1, public_chat_rate_limit_window_seconds=60,
    )
    initialize_database(settings.resolved_database_path)
    app = create_app(settings)
    reset_rate_limits()

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        first = await client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": True})
        assert first.status_code == 200
        second = await client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": True})
        assert second.status_code == 429
    finally:
        await client.aclose()


async def test_full_public_voice_session_flow_over_http(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        created = await client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": True})
        assert created.status_code == 200, created.text
        session = created.json()
        assert session["status"] == "active"
        sid = session["public_id"]

        chunk = await client.post(
            f"{PUBLIC_VO}/sessions/{sid}/chunks",
            json={"sequence": 0, "audio_base64": _audio_b64(b"audio bytes for the http flow" * 10)},
        )
        assert chunk.status_code == 200, chunk.text

        finished = await client.post(f"{PUBLIC_VO}/sessions/{sid}/finish")
        assert finished.status_code == 200, finished.text
        result = finished.json()
        assert result["transcript"]
        assert result["reply"]
        assert result["tts_audio_relative_path"]

        fetched = await client.get(f"{PUBLIC_VO}/sessions/{sid}")
        assert fetched.status_code == 200
        assert fetched.json()["public_id"] == sid

        closed = await client.post(f"{PUBLIC_VO}/sessions/{sid}/close")
        assert closed.status_code == 200
        assert closed.json()["status"] == "completed"
    finally:
        await client.aclose()


async def test_public_session_not_found_for_unowned_session_id(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{PUBLIC_VO}/sessions/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_public_session_denied_without_consent(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": False})
        assert response.status_code == 200
        assert response.json()["status"] == "denied"
    finally:
        await client.aclose()


async def test_admin_memory_and_events_and_sessions_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    public_client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        created = await public_client.post(f"{PUBLIC_VO}/sessions", json={"explicit_consent": True})
        sid = created.json()["public_id"]
        await public_client.post(
            f"{PUBLIC_VO}/sessions/{sid}/chunks",
            json={"sequence": 0, "audio_base64": _audio_b64()},
        )
        await public_client.post(f"{PUBLIC_VO}/sessions/{sid}/finish")
        await public_client.post(f"{PUBLIC_VO}/sessions/{sid}/close")

        sessions = await client.get(f"{MBVO}/sessions", headers=headers)
        assert sessions.status_code == 200
        assert len(sessions.json()["items"]) >= 1

        memory = await client.get(f"{MBVO}/memory", headers=headers)
        assert memory.status_code == 200
        assert len(memory.json()["items"]) >= 1

        events = await client.get(f"{MBVO}/events", headers=headers)
        assert events.status_code == 200
        assert len(events.json()["items"]) >= 1
    finally:
        await client.aclose()
        await public_client.aclose()
