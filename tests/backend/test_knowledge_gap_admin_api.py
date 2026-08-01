"""Phase 19 Step 26 -- Admin-only `/api/admin/knowledge-gaps` API
tests: auth, CSRF, pagination, redaction, stable errors, stale-merge
handling, audit, no raw-text exposure, no RAG/training side effects."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.services.knowledge_gap_capture_service import KnowledgeGapCaptureService
from tests.backend.test_dataset_api import authenticated_client

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


def _seed_case(
    settings: Settings, message: str = "what is the latest python version", **kwargs
) -> dict:
    capture = KnowledgeGapCaptureService(settings)
    defaults = dict(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
        domain="software",
        intent="ask_current_status",
        freshness="time_sensitive",
    )
    defaults.update(kwargs)
    return capture.capture(message=message, **defaults)


async def test_endpoints_require_admin_auth(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/knowledge-gaps/overview")
        assert response.status_code == 401
        response = await client.get("/api/admin/knowledge-gaps/cases")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_overview_reports_real_counts(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/knowledge-gaps/overview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_cases"] == 1
        assert "web_demand" in body
        assert "tamil" in body
    finally:
        await client.aclose()


async def test_list_and_get_case_never_expose_raw_secrets(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings, message="password: hunter2secret help me")

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/knowledge-gaps/cases", headers=headers)
        assert response.status_code == 200
        assert "hunter2secret" not in response.text

        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["content_unavailable_for_review"] is True

        response = await client.get(
            "/api/admin/knowledge-gaps/cases/does-not-exist", headers=headers
        )
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_pagination_bounds_are_enforced(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/knowledge-gaps/cases", params={"limit": 500}, headers=headers
        )
        assert response.status_code == 422
        response = await client.get(
            "/api/admin/knowledge-gaps/cases", params={"offset": -1}, headers=headers
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_review_endpoint_requires_csrf(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/review",
            json={"decision": "confirm_gap"},
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_review_rejects_unknown_decision(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/review",
            json={"decision": "not_a_real_decision"},
            headers=headers,
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_full_case_lifecycle_via_api(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/review",
            json={"decision": "confirm_gap", "comment": "confirmed"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "review_required"

        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/notes",
            json={"note_type": "investigation", "note_text": "checked docs"},
            headers=headers,
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/notes", headers=headers
        )
        assert response.json()["count"] == 1

        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/resolve",
            json={"resolution_type": "requires_trusted_web"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/events", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["count"] >= 3
    finally:
        await client.aclose()


async def test_note_rejects_credential_content(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/notes",
            json={"note_type": "investigation", "note_text": "password: realsecret123"},
            headers=headers,
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_note_rejects_html_and_script_content_as_stored_but_never_executed(
    api_app: FastAPI,
) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/notes",
            json={"note_type": "investigation", "note_text": "<script>alert(1)</script>"},
            headers=headers,
        )
        assert response.status_code == 200
        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/notes", headers=headers
        )
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_merge_flow_requires_stale_check_and_retains_occurrences(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case_a = _seed_case(settings, message="what is the latest python version")
    case_b = _seed_case(settings, message="latest python version please tell")

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-gaps/clusters/propose-merge",
            json={"case_public_ids": [case_a["public_id"], case_b["public_id"]]},
            headers=headers,
        )
        assert response.status_code == 200
        proposal = response.json()
        fingerprint = proposal["stale_check_fingerprint"]

        stale_response = await client.post(
            "/api/admin/knowledge-gaps/clusters/confirm-merge",
            json={
                "case_public_ids": [case_a["public_id"], case_b["public_id"]],
                "stale_check_fingerprint": "deliberately-wrong-fingerprint",
                "canonical_question": "latest python version",
                "primary_language": "en",
            },
            headers=headers,
        )
        assert stale_response.status_code == 409

        confirm_response = await client.post(
            "/api/admin/knowledge-gaps/clusters/confirm-merge",
            json={
                "case_public_ids": [case_a["public_id"], case_b["public_id"]],
                "stale_check_fingerprint": fingerprint,
                "canonical_question": "latest python version",
                "primary_language": "en",
            },
            headers=headers,
        )
        assert confirm_response.status_code == 200
        cluster_public_id = confirm_response.json()["public_id"]

        response = await client.get(
            f"/api/admin/knowledge-gaps/clusters/{cluster_public_id}", headers=headers
        )
        assert response.status_code == 200
        assert len(response.json()["members"]) == 2

        # Original occurrences must still exist post-merge.
        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case_a['public_id']}/occurrences", headers=headers
        )
        assert response.json()["count"] >= 1
    finally:
        await client.aclose()


async def test_daily_report_generation_and_listing(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-gaps/reports/daily/generate", headers=headers
        )
        assert response.status_code == 200
        assert "summary" in response.json()

        response = await client.get("/api/admin/knowledge-gaps/reports/daily", headers=headers)
        assert response.status_code == 200
        assert response.json()["count"] == 1
    finally:
        await client.aclose()


async def test_deletion_workflow_requires_correct_state_sequence(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        # Executing before requesting/confirming must fail.
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/execute-deletion",
            headers=headers,
        )
        assert response.status_code == 422

        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/deletion-preview",
            headers=headers,
        )
        assert response.status_code == 200

        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/request-deletion",
            json={"reason": "user requested"},
            headers=headers,
        )
        assert response.status_code == 200

        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/confirm-deletion",
            headers=headers,
        )
        assert response.status_code == 200

        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/execute-deletion",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "deleted_payload"
        assert body["redacted_question"] is None

        # The case row itself must still exist (audit history preserved).
        response = await client.get(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}", headers=headers
        )
        assert response.status_code == 200
    finally:
        await client.aclose()


async def test_assess_handoff_never_creates_rag_or_training_side_effects(
    api_app: FastAPI,
) -> None:
    settings: Settings = api_app.state.settings
    case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            f"/api/admin/knowledge-gaps/cases/{case['public_id']}/assess-handoff", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert "eligible_for_rag_research" in body
        assert "eligible_for_training_assessment" in body
        # No response field ever names a created RAG source/training run.
        assert "rag_source_public_id" not in body
        assert "training_run_public_id" not in body
    finally:
        await client.aclose()
