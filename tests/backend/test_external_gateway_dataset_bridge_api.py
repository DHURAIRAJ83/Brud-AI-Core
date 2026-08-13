"""MB-40: API tests for /admin/mini-brain/external-ai-gateway-dataset-bridge.

Auth/CSRF requirements over real HTTP, plus one real end-to-end route
test: a session is driven to `admin_accepted` at the service layer
using `MockProviderClient` (the same double MB-21's own tests use --
no real network call, and the gateway's real review logic is never
bypassed, only its provider client is swapped), then the actual export
is performed through a real HTTP POST to this bridge's route, against
the same database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.services.external_ai_provider_client import MockProviderClient
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

BRIDGE = "/api/admin/mini-brain/external-ai-gateway-dataset-bridge"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _build_accepted_session(settings: Settings, admin_id: str) -> str:
    gateway = MiniBrainExternalAiGatewayService(
        settings, provider_clients={"mock1": MockProviderClient(provider_key="mock1", canned_text="Real accepted-session export payload.")},
    )
    session = gateway.create_session(topic="API bridge test", purpose="data_acquisition_assistance", admin_id=admin_id)
    session_id = session["public_id"]
    gateway.run_validate_authorization_stage(session_id, authorization_note="api test authorization", admin_id=admin_id)
    gateway.run_sanitize_inputs_stage(session_id, admin_stated_need="api test need", admin_id=admin_id)
    gateway.run_select_providers_stage(session_id, requested_provider_keys=["mock1"], admin_id=admin_id)
    gateway.run_dispatch_requests_stage(session_id, admin_id=admin_id)
    gateway.run_collect_responses_stage(session_id, admin_id=admin_id)
    gateway.run_normalize_responses_stage(session_id, admin_id=admin_id)
    gateway.run_analyze_agreement_stage(session_id, admin_id=admin_id)
    gateway.run_build_evidence_stage(session_id, admin_id=admin_id)
    gateway.generate_report_stage(session_id, admin_id=admin_id)
    session = gateway.admin_review(session_id, decision="accept", admin_id=admin_id)
    assert session["status"] == "admin_accepted"
    return session_id


async def _admin_public_id(app: FastAPI, username: str) -> str:
    with database_connection(app.state.settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT public_id FROM admin_accounts WHERE username=?", (username,)
        ).fetchone()
    return row["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post(f"{BRIDGE}/sessions/bogus/export-to-dataset", json={})
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_export_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{BRIDGE}/sessions/bogus/export-to-dataset", json={})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_export_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"{BRIDGE}/sessions/does-not-exist/export-to-dataset", json={}, headers=headers,
        )
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_real_accepted_session_exports_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    admin_id = await _admin_public_id(api_app, "dataset-admin")
    session_id = _build_accepted_session(api_app.state.settings, admin_id)

    response = await client.post(
        f"{BRIDGE}/sessions/{session_id}/export-to-dataset", json={}, headers=headers,
    )
    try:
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["session_public_id"] == session_id
        assert len(body["created_record_public_ids"]) == 1
        assert body["ingest_to_rag"] is False

        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT status FROM dataset_records WHERE public_id=?",
                (body["created_record_public_ids"][0],),
            ).fetchone()
        assert row["status"] == "draft"

        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            event_rows = connection.execute(
                "SELECT event_type FROM audit_logs WHERE resource_public_id=? AND "
                "resource_type='external_gateway_dataset_bridge' ORDER BY id",
                (session_id,),
            ).fetchall()
        event_types = [row["event_type"] for row in event_rows]
        assert "external_gateway_dataset_export_started" in event_types
        assert "external_gateway_dataset_export_completed" in event_types
    finally:
        await client.aclose()


async def test_pending_session_export_returns_422_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    admin_id = await _admin_public_id(api_app, "dataset-admin")

    gateway = MiniBrainExternalAiGatewayService(
        api_app.state.settings,
        provider_clients={"mock1": MockProviderClient(provider_key="mock1", canned_text="not yet reviewed")},
    )
    session = gateway.create_session(topic="pending test", purpose="data_acquisition_assistance", admin_id=admin_id)
    session_id = session["public_id"]
    gateway.run_validate_authorization_stage(session_id, authorization_note="a", admin_id=admin_id)
    gateway.run_sanitize_inputs_stage(session_id, admin_stated_need="a", admin_id=admin_id)
    gateway.run_select_providers_stage(session_id, requested_provider_keys=["mock1"], admin_id=admin_id)
    gateway.run_dispatch_requests_stage(session_id, admin_id=admin_id)
    gateway.run_collect_responses_stage(session_id, admin_id=admin_id)
    gateway.run_normalize_responses_stage(session_id, admin_id=admin_id)
    gateway.run_analyze_agreement_stage(session_id, admin_id=admin_id)
    gateway.run_build_evidence_stage(session_id, admin_id=admin_id)
    gateway.generate_report_stage(session_id, admin_id=admin_id)
    # No admin_review() call at all -- still awaiting_admin_review.

    response = await client.post(
        f"{BRIDGE}/sessions/{session_id}/export-to-dataset", json={}, headers=headers,
    )
    try:
        assert response.status_code == 422
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) AS n FROM dataset_records").fetchone()["n"]
        assert count == 0
    finally:
        await client.aclose()
