import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Manual-Data-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(
            username="manual-data-admin", display_name="Manual Data Admin", password=PASSWORD
        )
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "manual-data-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_source(client, headers, *, source_code="SRC-MD-API-0001"):
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


async def create_record(client, headers, source_public_id, *, tamil_text="வணக்கம்"):
    response = await client.post(
        "/api/admin/manual-data",
        headers=headers,
        json={
            "record_type": "plain_text",
            "primary_language": "ta",
            "source_public_id": source_public_id,
            "content": {"tamil_text": tamil_text},
        },
    )
    assert response.status_code == 200
    return response.json()


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/manual-data")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/manual-data",
            json={
                "record_type": "plain_text",
                "content": {"tamil_text": "x"},
            },
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_create_requires_source(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/manual-data",
            headers=headers,
            json={"record_type": "plain_text", "content": {"tamil_text": "வணக்கம்"}},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_create_get_list_and_summary(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        created = await create_record(client, headers, source["public_id"])
        assert created["status"] == "draft"
        assert created["source_public_id"] == source["public_id"]

        fetched = await client.get(f"/api/admin/manual-data/{created['public_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["active_revision"]["tamil_text"] == "வணக்கம்"

        listing = await client.get("/api/admin/manual-data")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        summary = await client.get("/api/admin/manual-data/summary")
        assert summary.status_code == 200
        assert summary.json()["total"] == 1
        assert summary.json()["by_status"]["draft"] == 1
    finally:
        await client.aclose()


async def test_not_found_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/manual-data/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        body = response.json()
        assert "traceback" not in str(body).lower()
        assert "sqlite" not in str(body).lower()
    finally:
        await client.aclose()


async def test_duplicate_content_returns_409(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-DUP-API")
        await create_record(client, headers, source["public_id"])
        response = await client.post(
            "/api/admin/manual-data",
            headers=headers,
            json={
                "record_type": "plain_text",
                "primary_language": "ta",
                "source_public_id": source["public_id"],
                "content": {"tamil_text": "வணக்கம்"},
            },
        )
        assert response.status_code == 409
    finally:
        await client.aclose()


async def test_lifecycle_review_verify_approve_flow(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-LIFECYCLE-API")
        # Rights must allow rag/training before approval can grant them.
        await client.put(
            f"/api/admin/data-sources/{source['public_id']}/rights",
            headers=headers,
            json={
                "rights_status": "licensed",
                "rag_use_allowed": True,
                "training_use_allowed": True,
            },
        )

        record = await create_record(client, headers, source["public_id"], tamil_text="ஒன்று")
        record_id = record["public_id"]

        submitted = await client.post(
            f"/api/admin/manual-data/{record_id}/submit-review", headers=headers
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "needs_review"

        reviewed = await client.post(
            f"/api/admin/manual-data/{record_id}/review",
            headers=headers,
            json={"review_type": "language", "review_status": "approved", "naturalness_score": 95},
        )
        assert reviewed.status_code == 200

        quality = await client.post(
            f"/api/admin/manual-data/{record_id}/quality-check", headers=headers
        )
        assert quality.status_code == 200
        assert quality.json()["blocking_issues"] == []

        approved = await client.post(
            f"/api/admin/manual-data/{record_id}/approve",
            headers=headers,
            json={"approved_uses": ["rag", "training"]},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert set(approved.json()["approved_uses"]) == {"rag", "training"}

        usage = await client.get(f"/api/admin/manual-data/{record_id}/usage-summary")
        assert usage.status_code == 200
        assert usage.json()["rag"]["allowed"] is True
    finally:
        await client.aclose()


async def test_approve_blocked_by_quality_gate_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-HIGHRISK-API")
        created = await client.post(
            "/api/admin/manual-data",
            headers=headers,
            json={
                "record_type": "knowledge_note",
                "primary_language": "en",
                "knowledge_risk": "high_risk",
                "fact_dependency": "high",
                "source_public_id": source["public_id"],
                "content": {"title": "Medical note", "input_text": "..."},
            },
        )
        assert created.status_code == 200
        record_id = created.json()["public_id"]
        await client.post(f"/api/admin/manual-data/{record_id}/submit-review", headers=headers)

        blocked = await client.post(
            f"/api/admin/manual-data/{record_id}/approve",
            headers=headers,
            json={"approved_uses": ["rag"]},
        )
        assert blocked.status_code == 422

        supporting = await create_source(client, headers, source_code="SRC-MD-SUPPORT-API")
        verified = await client.post(
            f"/api/admin/manual-data/{record_id}/verify",
            headers=headers,
            json={
                "verification_type": "factual_verification",
                "verification_status": "verified",
                "source_public_id": supporting["public_id"],
            },
        )
        assert verified.status_code == 200

        now_ok = await client.post(
            f"/api/admin/manual-data/{record_id}/approve",
            headers=headers,
            json={"approved_uses": ["rag"]},
        )
        assert now_ok.status_code == 200
    finally:
        await client.aclose()


async def test_revision_and_history(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-REV-API")
        record = await create_record(client, headers, source["public_id"], tamil_text="இரண்டு")
        record_id = record["public_id"]

        revised = await client.post(
            f"/api/admin/manual-data/{record_id}/revisions",
            headers=headers,
            json={"content": {"tamil_text": "இரண்டு -- திருத்தப்பட்டது"}, "change_summary": "fix"},
        )
        assert revised.status_code == 200

        revisions = await client.get(f"/api/admin/manual-data/{record_id}/revisions")
        assert revisions.status_code == 200
        assert len(revisions.json()["items"]) == 2

        history = await client.get(f"/api/admin/manual-data/{record_id}/history")
        assert history.status_code == 200
        assert any(e["event_type"] == "record_created" for e in history.json()["events"])
    finally:
        await client.aclose()


async def test_reject_and_archive_restore(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-REJECT-API")
        record = await create_record(client, headers, source["public_id"], tamil_text="மூன்று")
        record_id = record["public_id"]

        await client.post(f"/api/admin/manual-data/{record_id}/submit-review", headers=headers)
        rejected = await client.post(
            f"/api/admin/manual-data/{record_id}/reject",
            headers=headers,
            json={"reason": "not natural"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        archived = await client.post(f"/api/admin/manual-data/{record_id}/archive", headers=headers)
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

        restored = await client.post(f"/api/admin/manual-data/{record_id}/restore", headers=headers)
        assert restored.status_code == 200
        assert restored.json()["status"] == "draft"
    finally:
        await client.aclose()


async def test_invalid_transition_returns_422_not_500(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-BADTRANSITION-API")
        record = await create_record(client, headers, source["public_id"], tamil_text="ஆறு")
        record_id = record["public_id"]

        # A fresh draft record cannot jump straight to approved.
        response = await client.post(
            f"/api/admin/manual-data/{record_id}/approve",
            headers=headers,
            json={"approved_uses": []},
        )
        assert response.status_code == 422
        body = response.json()
        assert "traceback" not in str(body).lower()
    finally:
        await client.aclose()


async def test_create_dataset_candidate(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-CANDIDATE-API")
        record = await create_record(client, headers, source["public_id"], tamil_text="நான்கு")
        record_id = record["public_id"]

        await client.post(f"/api/admin/manual-data/{record_id}/submit-review", headers=headers)
        not_yet_approved = await client.post(
            f"/api/admin/manual-data/{record_id}/create-dataset-candidate",
            headers=headers,
            json={},
        )
        assert not_yet_approved.status_code == 422

        await client.post(
            f"/api/admin/manual-data/{record_id}/approve",
            headers=headers,
            json={"approved_uses": []},
        )
        candidate = await client.post(
            f"/api/admin/manual-data/{record_id}/create-dataset-candidate",
            headers=headers,
            json={"notes": "ready for dataset"},
        )
        assert candidate.status_code == 200
        assert candidate.json()["exported_dataset_record_public_id"]

        # A second export attempt must not create a duplicate dataset record.
        duplicate = await client.post(
            f"/api/admin/manual-data/{record_id}/create-dataset-candidate",
            headers=headers,
            json={},
        )
        assert duplicate.status_code == 409
    finally:
        await client.aclose()


async def test_every_mutation_is_audited(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers, source_code="SRC-MD-AUDIT-API")
        record = await create_record(client, headers, source["public_id"], tamil_text="ஐந்து")
        await client.post(f"/api/admin/manual-data/{record['public_id']}/archive", headers=headers)

        audit = await client.get("/api/admin/audit/recent?limit=50")
        assert audit.status_code == 200
        events = {item["event_type"] for item in audit.json()["items"]}
        assert "manual_data_record_created" in events
        assert "manual_data_archived" in events
    finally:
        await client.aclose()
