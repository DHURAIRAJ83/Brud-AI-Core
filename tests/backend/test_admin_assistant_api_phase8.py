import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Assistant-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="assistant-admin", display_name="Assistant Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "assistant-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def test_pages_endpoint_lists_every_dashboard_page(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
        try:
            assert (await unauthenticated.get("/api/admin/assistant/pages")).status_code == 401
        finally:
            await unauthenticated.aclose()

        response = await client.get("/api/admin/assistant/pages")
        assert response.status_code == 200
        body = response.json()
        assert body["registry_version"] == "v1"
        page_ids = {item["page_id"] for item in body["items"]}
        assert "datasets" in page_ids
        assert "chat_testing" in page_ids
        chat_testing = next(item for item in body["items"] if item["page_id"] == "chat_testing")
        assert chat_testing["implemented"] is False
    finally:
        await client.aclose()


async def test_actions_endpoint_exposes_registry_metadata(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/assistant/actions")
        assert response.status_code == 200
        body = response.json()
        assert "dataset_record_review" in body["action_types"]
        assert not any("train" in item for item in body["action_types"])
        override = next(
            a for a in body["actions"] if a["action_type"] == "governance_target_approval_override"
        )
        assert override["risk_level"] == "high"
        assert override["requires_reason"] is True
    finally:
        await client.aclose()


async def test_health_endpoint_reports_no_llm_available_by_default(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/assistant/health")
        assert response.status_code == 200
        body = response.json()
        assert body["llm_available"] is False
        assert body["scope_key"] == "admin_diagnostic"
    finally:
        await client.aclose()


async def test_chat_endpoint_greeting_flow(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/assistant/chat",
            headers=headers,
            json={"message": "Hello", "page_id": "overview"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "greeting"
        assert body["status"] == "completed"
    finally:
        await client.aclose()


async def test_chat_endpoint_open_ended_falls_back_without_llm(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/assistant/chat",
            headers=headers,
            json={
                "message": "Why did the last evaluation run score lower than expected?",
                "page_id": "evaluation",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "open_ended"
        assert body["status"] == "generation_failed"
    finally:
        await client.aclose()


async def test_chat_endpoint_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/assistant/chat", json={"message": "Hello", "page_id": "overview"}
        )
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_feedback_endpoint_accepts_valid_rating_and_rejects_invalid(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        good = await client.post(
            "/api/admin/assistant/feedback",
            headers=headers,
            json={"rating": "helpful", "page_id": "datasets", "comment": "Clear guidance"},
        )
        assert good.status_code == 200
        assert good.json()["rating"] == "helpful"

        bad = await client.post(
            "/api/admin/assistant/feedback",
            headers=headers,
            json={"rating": "not_a_real_rating"},
        )
        assert bad.status_code == 422
    finally:
        await client.aclose()


async def test_cancel_endpoint_withdraws_a_pending_proposal(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        proposed = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "dataset_source_update",
                "target_type": "dataset_source",
                "target_public_id": "does-not-exist",
                "summary": "Rename",
                "request_payload": {"name": "New Name"},
            },
        )
        assert proposed.status_code == 200
        public_id = proposed.json()["public_id"]

        cancelled = await client.post(
            f"/api/admin/assistant/proposals/{public_id}/cancel",
            headers=headers,
            json={"reason": "changed my mind"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        cancel_again = await client.post(
            f"/api/admin/assistant/proposals/{public_id}/cancel",
            headers=headers,
            json={},
        )
        assert cancel_again.status_code == 422

        audit = await client.get("/api/admin/audit/recent?limit=50")
        events = {item["event_type"] for item in audit.json()["items"]}
        assert "admin_assistant_proposal_cancelled" in events
    finally:
        await client.aclose()


async def test_high_risk_action_proposal_requires_reason(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "governance_target_approval_override",
                "target_type": "governance_entity",
                "target_public_id": "dataset-record-api-test-1",
                "summary": "Override rag eligibility",
                "request_payload": {
                    "entity_type": "dataset_record",
                    "target_use": "rag",
                    "decision": "allowed",
                },
            },
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_high_risk_action_full_propose_review_execute_flow(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        proposed = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "governance_target_approval_override",
                "target_type": "governance_entity",
                "target_public_id": "dataset-record-api-test-2",
                "summary": "Override rag eligibility",
                "request_payload": {
                    "entity_type": "dataset_record",
                    "target_use": "rag",
                    "decision": "allowed",
                    "reason": "manually verified licence",
                },
            },
        )
        assert proposed.status_code == 200
        proposal = proposed.json()
        assert proposal["risk_level"] == "high"
        assert proposal["preview"]["proposed_state"]["decision"] == "allowed"

        reviewed = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/review",
            headers=headers,
            json={"decision": "approved", "comment": None},
        )
        assert reviewed.status_code == 200

        executed = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/execute", headers=headers
        )
        assert executed.status_code == 200
        assert executed.json()["execution_result"]["decision"] == "allowed"
    finally:
        await client.aclose()
