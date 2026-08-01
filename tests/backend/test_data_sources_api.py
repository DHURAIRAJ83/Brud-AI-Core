import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Data-Sources-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(
            username="data-sources-admin", display_name="Data Sources Admin", password=PASSWORD
        )
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "data-sources-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_source(
    client, headers, *, source_code="SRC-API-0001", source_type="human_created"
):
    response = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={"source_code": source_code, "title": "Test source", "source_type": source_type},
    )
    assert response.status_code == 200
    return response.json()


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/data-sources")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/data-sources",
            json={"source_code": "SRC-NOCSRF", "title": "X", "source_type": "human_created"},
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_create_get_list_update_source(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(client, headers)
        assert created["status"] == "draft"

        fetched = await client.get(f"/api/admin/data-sources/{created['public_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Test source"

        listing = await client.get("/api/admin/data-sources")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        updated = await client.patch(
            f"/api/admin/data-sources/{created['public_id']}",
            headers=headers,
            json={"title": "Updated title"},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated title"
    finally:
        await client.aclose()


async def test_list_filters_by_status_type_and_search(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await create_source(
            client, headers, source_code="SRC-FILTER-GOV", source_type="government_source"
        )
        await create_source(
            client, headers, source_code="SRC-FILTER-HUMAN", source_type="human_created"
        )

        by_type = await client.get(
            "/api/admin/data-sources", params={"source_type": "government_source"}
        )
        assert by_type.json()["total"] == 1

        by_status = await client.get("/api/admin/data-sources", params={"status": "draft"})
        assert by_status.json()["total"] == 2

        by_search = await client.get(
            "/api/admin/data-sources", params={"search": "SRC-FILTER-HUMAN"}
        )
        assert by_search.json()["total"] == 1
    finally:
        await client.aclose()


async def test_not_found_returns_404_without_raw_db_error(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/data-sources/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        body = response.json()
        assert "traceback" not in str(body).lower()
        assert "sqlite" not in str(body).lower()
    finally:
        await client.aclose()


async def test_archive_restore_and_invalid_transition(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(client, headers, source_code="SRC-ARCHIVE-API")
        archived = await client.post(
            f"/api/admin/data-sources/{created['public_id']}/archive", headers=headers
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

        # Archived sources refuse edits.
        blocked = await client.patch(
            f"/api/admin/data-sources/{created['public_id']}", headers=headers, json={"title": "X"}
        )
        assert blocked.status_code == 422

        restored = await client.post(
            f"/api/admin/data-sources/{created['public_id']}/restore", headers=headers
        )
        assert restored.status_code == 200
        assert restored.json()["status"] == "draft"

        # archived -> archived directly (skipping draft) is not a valid transition.
        invalid = await client.post(
            f"/api/admin/data-sources/{created['public_id']}/verify",
            headers=headers,
            json={"action": "document_verify"},
        )
        assert invalid.status_code == 422
    finally:
        await client.aclose()


async def test_rights_full_lifecycle_and_usage_check(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(
            client, headers, source_code="SRC-LIFECYCLE-API", source_type="open_dataset"
        )
        source_id = created["public_id"]

        no_rights = await client.get(f"/api/admin/data-sources/{source_id}/rights")
        assert no_rights.status_code == 200
        assert no_rights.json() is None

        blocked_check = await client.post(
            f"/api/admin/data-sources/{source_id}/usage-check",
            headers=headers,
            json={"target_use": "training"},
        )
        assert blocked_check.status_code == 200
        assert blocked_check.json()["allowed"] is False
        assert blocked_check.json()["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"

        rights = await client.put(
            f"/api/admin/data-sources/{source_id}/rights",
            headers=headers,
            json={
                "rights_status": "open_license",
                "license_name": "CC BY 4.0",
                "training_use_allowed": True,
                "rag_use_allowed": True,
            },
        )
        assert rights.status_code == 200

        submitted = await client.post(
            f"/api/admin/data-sources/{source_id}/submit-review", headers=headers
        )
        assert submitted.status_code == 200
        assert submitted.json()["rights_status"] == "open_license"

        verified = await client.post(
            f"/api/admin/data-sources/{source_id}/verify",
            headers=headers,
            json={"action": "document_verify", "evidence_reference": "licence.pdf"},
        )
        assert verified.status_code == 200
        assert verified.json()["status"] == "verified"

        allowed_check = await client.post(
            f"/api/admin/data-sources/{source_id}/usage-check",
            headers=headers,
            json={"target_use": "training"},
        )
        assert allowed_check.status_code == 200
        assert allowed_check.json()["allowed"] is True

        summary = await client.get(f"/api/admin/data-sources/{source_id}/usage-summary")
        assert summary.status_code == 200
        assert set(summary.json()) == {
            "rag",
            "training",
            "evaluation",
            "commercial",
            "public_export",
            "redistribution",
        }

        events = await client.get(f"/api/admin/data-sources/{source_id}/verification-events")
        assert events.status_code == 200
        assert len(events.json()["items"]) == 1

        history = await client.get(f"/api/admin/data-sources/{source_id}/history")
        assert history.status_code == 200
        # Two explicit training checks (blocked, then allowed) plus one more
        # from the usage-summary call above evaluating every target use.
        training_decisions = [
            item for item in history.json()["usage_decisions"] if item["target_use"] == "training"
        ]
        assert len(training_decisions) == 3
        assert training_decisions[0]["decision_code"] == "ALLOWED"  # most recent (summary)
        assert training_decisions[-1]["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"  # oldest
    finally:
        await client.aclose()


async def test_invalid_rights_combination_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(client, headers, source_code="SRC-INVALID-API")
        response = await client.put(
            f"/api/admin/data-sources/{created['public_id']}/rights",
            headers=headers,
            json={"public_export_allowed": True, "redistribution_allowed": False},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_link_create_list_delete(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(client, headers, source_code="SRC-LINK-API")
        source_id = created["public_id"]

        link = await client.post(
            f"/api/admin/data-sources/{source_id}/links",
            headers=headers,
            json={"entity_type": "dataset_record", "entity_public_id": "record-xyz"},
        )
        assert link.status_code == 200
        link_id = link.json()["public_id"]

        listed = await client.get(f"/api/admin/data-sources/{source_id}/links")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        deleted = await client.delete(
            f"/api/admin/data-sources/{source_id}/links/{link_id}", headers=headers
        )
        assert deleted.status_code == 200

        listed_after = await client.get(f"/api/admin/data-sources/{source_id}/links")
        assert listed_after.json()["items"] == []
    finally:
        await client.aclose()


async def test_duplicate_source_code_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await create_source(client, headers, source_code="SRC-DUP-API")
        response = await client.post(
            "/api/admin/data-sources",
            headers=headers,
            json={"source_code": "SRC-DUP-API", "title": "Second", "source_type": "human_created"},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_every_mutation_is_audited(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await create_source(client, headers, source_code="SRC-AUDIT-API")
        await client.post(
            f"/api/admin/data-sources/{created['public_id']}/archive", headers=headers
        )

        audit = await client.get("/api/admin/audit/recent?limit=50")
        assert audit.status_code == 200
        events = {item["event_type"] for item in audit.json()["items"]}
        assert "data_source_created" in events
        assert "data_source_archived" in events
    finally:
        await client.aclose()
