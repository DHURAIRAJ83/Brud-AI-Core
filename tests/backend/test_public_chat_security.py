"""Phase 18 Step 34/36 -- security, privacy, and false-route-control
tests for the public Smart Answer Router. Complements the worked
end-to-end examples already in `test_public_chat_routing_service.py`
and the honest-placeholder-replacement tests in `test_api.py`."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.models.public_chat import MAX_MESSAGE_LENGTH
from backend.services.public_chat_rate_limiter import reset_rate_limits

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
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def api_request(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


# -- request-shape hardening -----------------------------------------------------------------


async def test_oversized_message_is_rejected(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "a" * (MAX_MESSAGE_LENGTH + 1)}
    )
    assert response.status_code == 422


async def test_unknown_fields_are_rejected_including_admin_style_overrides(
    api_app: FastAPI,
) -> None:
    """No public request field may select an arbitrary model/RAG-space/
    provider/checkpoint id -- the schema doesn't define such a field, and
    `extra="forbid"` (the repo-wide convention) means an attempt to smuggle
    one in is rejected outright rather than silently ignored."""

    for bad_field, value in (
        ("model_assignment_id", "1"),
        ("rag_space_id", "1"),
        ("provider", "openai"),
        ("checkpoint_path", "/core_models/checkpoints/x"),
        ("admin_override", True),
    ):
        response = await api_request(
            api_app, "POST", "/api/chat", json={"message": "hello", bad_field: value}
        )
        assert response.status_code == 422, bad_field


async def test_malformed_json_body_returns_stable_error_not_a_stack_trace(
    api_app: FastAPI,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat", content=b"{not valid json", headers={"content-type": "application/json"}
        )
    assert response.status_code == 422
    body = response.json()
    assert "Traceback" not in str(body)
    assert "File \"" not in str(body)


@pytest.mark.parametrize(
    "message",
    [
        "hello\x00world",  # null byte
        "hello​world",  # zero-width space
        "‮hello‬",  # right-to-left override (bidi)
        "<script>alert(1)</script>",
        "'; DROP TABLE public_chat_routing_events; --",
    ],
)
async def test_hostile_input_bytes_never_crash_the_router(
    api_app: FastAPI, message: str
) -> None:
    """None of these should ever produce a 500 -- the router must
    degrade to an honest routed response (any of the six routes) for
    any input shape, never leak an internal exception."""

    response = await api_request(api_app, "POST", "/api/chat", json={"message": message})
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        body = response.json()
        assert body["route_used"] in (
            "core_model", "approved_rag", "memory", "clarify", "refuse", "insufficient",
        )


async def test_sql_like_input_does_not_corrupt_or_error_the_database(api_app: FastAPI) -> None:
    response = await api_request(
        api_app,
        "POST",
        "/api/chat",
        json={"message": "'; DROP TABLE public_chat_routing_events; --"},
    )
    assert response.status_code == 200
    # The events table must still be queryable afterwards -- proves the
    # parameterized-query convention held and nothing was actually dropped.
    follow_up = await api_request(api_app, "POST", "/api/chat", json={"message": "hello again"})
    assert follow_up.status_code == 200


# -- rate limiting -----------------------------------------------------------------------------


async def test_repeated_requests_beyond_the_limit_are_rate_limited(tmp_path: Path) -> None:
    reset_rate_limits()
    settings = Settings(
        database_path=tmp_path / "rl.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
        public_chat_rate_limit_max_requests=2,
        public_chat_rate_limit_window_seconds=60,
    )
    initialize_database(settings.resolved_database_path)
    app = create_app(settings)
    try:
        responses = [
            await api_request(app, "POST", "/api/chat", json={"message": f"hi {i}"})
            for i in range(4)
        ]
    finally:
        reset_rate_limits()
    statuses = [response.status_code for response in responses]
    assert statuses[:2] == [200, 200]
    assert 429 in statuses
    limited = responses[statuses.index(429)]
    assert limited.json()["error"]["code"] == "CHAT_RATE_LIMITED"


# -- privacy: no internal identifiers ever reach the public response --------------------------


async def test_response_never_exposes_internal_identifiers_or_paths(api_app: FastAPI) -> None:
    response = await api_request(api_app, "POST", "/api/chat", json={"message": "வணக்கம்"})
    assert response.status_code == 200
    body_text = response.text
    for forbidden in ("checkpoint", "system_prompt", "/core_models/", "/database/", "api_key"):
        assert forbidden not in body_text


async def test_feedback_endpoint_rejects_unknown_feedback_type(api_app: FastAPI) -> None:
    response = await api_request(
        api_app,
        "POST",
        "/api/chat/feedback",
        json={
            "request_id": "req-1",
            "route_used": "core_model",
            "answer_hash": "a" * 64,
            "feedback_type": "not_a_real_category",
        },
    )
    assert response.status_code == 422


# -- admin diagnostics: never exposes raw text even under adversarial content -----------------


async def test_hostile_message_never_appears_verbatim_in_admin_diagnostics(
    api_app: FastAPI,
) -> None:
    from tests.backend.test_dataset_api import authenticated_client

    hostile = "<script>alert('xss')</script> secret-looking-token-abc123"
    await api_request(api_app, "POST", "/api/chat", json={"message": hostile})

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/public-chat-routing/events", headers=headers)
        assert response.status_code == 200
        assert "<script>" not in response.text
        assert "secret-looking-token-abc123" not in response.text
    finally:
        await client.aclose()
