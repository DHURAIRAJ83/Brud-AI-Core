import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Governance-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="gov-admin", display_name="Governance Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "gov-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_source(client, headers, *, source_code="SRC-GOV-API-0001"):
    response = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={
            "source_code": source_code,
            "title": "Dhurai -- Spoken Tamil",
            "source_type": "human_created",
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_record(client, headers, source_public_id, *, word="ஒன்று"):
    response = await client.post(
        "/api/admin/manual-data",
        headers=headers,
        json={
            "record_type": "dictionary_entry",
            "primary_language": "ta",
            "source_public_id": source_public_id,
            "content": {"word": word, "meanings": ["one"]},
        },
    )
    assert response.status_code == 200
    return response.json()


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/data-governance/queue")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/data-governance/review/open",
            json={
                "entity_type": "document_page",
                "entity_public_id": "page-x",
                "reason": "submitted_for_review",
            },
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_open_review_item_is_idempotent_and_appears_in_queue(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        first = await client.post(
            "/api/admin/data-governance/review/open",
            headers=headers,
            json={
                "entity_type": "document_page",
                "entity_public_id": "page-api-1",
                "reason": "submitted_for_review",
                "priority": "high",
            },
        )
        assert first.status_code == 200
        second = await client.post(
            "/api/admin/data-governance/review/open",
            headers=headers,
            json={
                "entity_type": "document_page",
                "entity_public_id": "page-api-1",
                "reason": "submitted_for_review",
            },
        )
        assert second.status_code == 200
        assert first.json()["public_id"] == second.json()["public_id"]

        detail = await client.get(
            f"/api/admin/data-governance/review/{first.json()['public_id']}"
        )
        assert detail.status_code == 200
        assert detail.json()["issues"] == []

        queue = await client.get(
            "/api/admin/data-governance/queue", params={"entity_type": "document_page"}
        )
        assert queue.status_code == 200
        assert any(
            item["entity_public_id"] == "page-api-1" for item in queue.json()["items"]
        )
    finally:
        await client.aclose()


async def test_assign_status_and_note(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        opened = await client.post(
            "/api/admin/data-governance/review/open",
            headers=headers,
            json={
                "entity_type": "document_page",
                "entity_public_id": "page-api-2",
                "reason": "submitted_for_review",
            },
        )
        review_id = opened.json()["public_id"]

        assigned = await client.post(
            f"/api/admin/data-governance/review/{review_id}/assign",
            headers=headers,
            json={"assignee_admin_public_id": "admin-2"},
        )
        assert assigned.status_code == 200
        assert assigned.json()["assigned_admin_public_id"] == "admin-2"

        noted = await client.post(
            f"/api/admin/data-governance/review/{review_id}/note",
            headers=headers,
            json={"note": "looks fine so far"},
        )
        assert noted.status_code == 200

        resolved = await client.post(
            f"/api/admin/data-governance/review/{review_id}/status",
            headers=headers,
            json={"status": "resolved", "notes": "nothing else to check"},
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"

        history = await client.get(f"/api/admin/data-governance/review/{review_id}/history")
        assert history.status_code == 200
        event_types = {item["event_type"] for item in history.json()["items"]}
        assert "review_item_assigned" in event_types
        assert "note_added" in event_types
        assert "review_item_status_changed" in event_types
    finally:
        await client.aclose()


async def test_approval_evaluate_status_and_override(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-GOV-API-APPROVAL")
        record = await create_record(client, headers, source["public_id"], word="இரண்டு")
        record_id = record["public_id"]

        blocked = await client.post(
            f"/api/admin/data-governance/approvals/manual_data_record/{record_id}/training"
            "/evaluate",
            headers=headers,
        )
        assert blocked.status_code == 200
        assert blocked.json()["decision"] == "blocked"

        matrix = await client.get(
            f"/api/admin/data-governance/approvals/manual_data_record/{record_id}"
        )
        assert matrix.status_code == 200
        assert matrix.json()["targets"]["commercial"]["decision"] == "not_requested"

        readiness = await client.get(
            f"/api/admin/data-governance/export-readiness/manual_data_record/{record_id}"
            "/training"
        )
        assert readiness.status_code == 200
        assert readiness.json()["decision"] == "blocked"

        override_missing_reason = await client.post(
            f"/api/admin/data-governance/approvals/manual_data_record/{record_id}/training"
            "/override",
            headers=headers,
            json={"decision": "allowed", "reason": ""},
        )
        assert override_missing_reason.status_code == 422

        overridden = await client.post(
            f"/api/admin/data-governance/approvals/manual_data_record/{record_id}/training"
            "/override",
            headers=headers,
            json={"decision": "allowed", "reason": "legal separately cleared this"},
        )
        assert overridden.status_code == 200
        assert overridden.json()["decision"] == "allowed"
        assert overridden.json()["is_override"] == 1
    finally:
        await client.aclose()


async def test_duplicate_and_conflict_group_listing_endpoints(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        duplicates = await client.get("/api/admin/data-governance/duplicates")
        assert duplicates.status_code == 200
        assert duplicates.json() == {"items": []}

        conflicts = await client.get("/api/admin/data-governance/conflicts")
        assert conflicts.status_code == 200
        assert conflicts.json() == {"items": []}

        sync = await client.post(
            "/api/admin/data-governance/duplicates/manual-data/"
            "00000000-0000-0000-0000-000000000000/sync",
            headers=headers,
        )
        assert sync.status_code == 404
    finally:
        await client.aclose()
