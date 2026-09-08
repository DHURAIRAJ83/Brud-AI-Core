import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Assistant-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    admin = AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="assistant-admin", display_name="Assistant Admin", password=PASSWORD)
    )
    # Phase 4: this suite exercises the full propose/review/execute HTTP
    # flow end to end for an already-authorized admin -- RBAC denial
    # itself is covered by tests/database/test_admin_write_governance.py.
    # Granting SUPER_ADMIN here keeps this suite's pre-Phase-4 execute
    # assertions valid without touching AdminAssistantService itself.
    app.state.settings.admin_role_overrides = f"{admin.public_id}:SUPER_ADMIN"
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "assistant-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_pending_record(client, headers):
    source = (
        await client.post(
            "/api/admin/datasets/sources",
            headers=headers,
            json={"name": "Assistant Source", "language": "ta", "source_type": "manual"},
        )
    ).json()
    record = (
        await client.post(
            "/api/admin/datasets/records",
            headers=headers,
            json={
                "source_public_id": source["public_id"],
                "record_type": "instruction",
                "language": "ta",
                "instruction": "Say hello",
                "output_text": "வணக்கம்",
                "metadata": {},
            },
        )
    ).json()
    submitted = await client.post(
        f"/api/admin/datasets/records/{record['public_id']}/submit", headers=headers
    )
    assert submitted.json()["status"] == "pending_review"
    return record


async def test_overview_and_actions_are_readable(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/assistant/overview")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()
    try:
        overview = await client.get("/api/admin/assistant/overview")
        assert overview.status_code == 200
        assert "guidance" in overview.json() and "summary" in overview.json()
        actions = (await client.get("/api/admin/assistant/actions")).json()
        assert "dataset_record_review" in actions["action_types"]
        assert not any("train" in item for item in actions["action_types"])
    finally:
        await client.aclose()


async def test_propose_review_execute_flow_mutates_only_after_approval(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        record = await create_pending_record(client, headers)

        proposed = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "dataset_record_review",
                "target_type": "dataset_record",
                "target_public_id": record["public_id"],
                "summary": "Approve the Tamil greeting record",
                "request_payload": {"decision": "approve", "comments": "Looks correct"},
            },
        )
        assert proposed.status_code == 200
        proposal = proposed.json()
        assert proposal["status"] == "pending"
        assert proposal["execution_status"] == "not_applicable"

        # The record must remain untouched until an admin approves and executes.
        unchanged = await client.get(f"/api/admin/datasets/records/{record['public_id']}")
        assert unchanged.json()["status"] == "pending_review"

        blocked_execute = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/execute", headers=headers
        )
        assert blocked_execute.status_code == 422

        reviewed = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/review",
            headers=headers,
            json={"decision": "approved", "comment": "Confirmed correct"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "approved"
        assert reviewed.json()["execution_status"] == "pending"

        double_review = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/review",
            headers=headers,
            json={"decision": "approved", "comment": None},
        )
        assert double_review.status_code == 422

        executed = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/execute", headers=headers
        )
        assert executed.status_code == 200
        body = executed.json()
        assert body["execution_status"] == "succeeded"
        assert body["execution_result"]["status"] == "approved"

        record_after = await client.get(f"/api/admin/datasets/records/{record['public_id']}")
        assert record_after.json()["status"] == "approved"

        double_execute = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/execute", headers=headers
        )
        assert double_execute.status_code == 422

        audit = await client.get("/api/admin/audit/recent?limit=50")
        events = {item["event_type"] for item in audit.json()["items"]}
        assert {
            "admin_assistant_proposal_created",
            "admin_review_approved",
            "admin_assistant_proposal_executed",
        } <= events
    finally:
        await client.aclose()


async def test_rejected_proposal_cannot_be_executed(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        record = await create_pending_record(client, headers)
        proposed = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "dataset_record_review",
                "target_type": "dataset_record",
                "target_public_id": record["public_id"],
                "summary": "Reject this record",
                "request_payload": {"decision": "reject", "comments": "Not accurate"},
            },
        )
        proposal = proposed.json()
        rejected = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/review",
            headers=headers,
            json={"decision": "rejected", "comment": "Not needed"},
        )
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["execution_status"] == "not_applicable"

        execute_after_reject = await client.post(
            f"/api/admin/assistant/proposals/{proposal['public_id']}/execute", headers=headers
        )
        assert execute_after_reject.status_code == 422

        record_after = await client.get(f"/api/admin/datasets/records/{record['public_id']}")
        assert record_after.json()["status"] == "pending_review"

        audit = await client.get("/api/admin/audit/recent?limit=50")
        events = {item["event_type"] for item in audit.json()["items"]}
        assert "admin_review_rejected" in events
    finally:
        await client.aclose()


async def test_unsupported_action_type_is_rejected_at_proposal_time(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/assistant/proposals",
            headers=headers,
            json={
                "action_type": "start_training_job",
                "target_type": "training_job",
                "target_public_id": "whatever",
                "summary": "Start training",
                "request_payload": {},
            },
        )
        assert response.status_code == 422
        assert "not permitted" in response.json()["error"]["message"] or "unsupported" in (
            response.json()["error"]["message"]
        )

        listing = await client.get("/api/admin/assistant/proposals")
        assert listing.json() == []
    finally:
        await client.aclose()
