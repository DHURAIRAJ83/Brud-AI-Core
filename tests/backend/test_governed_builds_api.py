import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Governed-Build-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="gbr-admin", display_name="Governed Build Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "gbr-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_approved_record(client, headers, *, name_suffix="1", text="Approved text."):
    source = await client.post(
        "/api/admin/datasets/sources",
        headers=headers,
        json={"name": f"Governed Build API Source {name_suffix}", "language": "en"},
    )
    assert source.status_code == 200
    record = await client.post(
        "/api/admin/datasets/records",
        headers=headers,
        json={
            "source_public_id": source.json()["public_id"],
            "record_type": "pretrain",
            "language": "en",
            "input_text": text,
        },
    )
    assert record.status_code == 200
    record_public_id = record.json()["public_id"]
    submitted = await client.post(
        f"/api/admin/datasets/records/{record_public_id}/submit", headers=headers
    )
    assert submitted.status_code == 200
    approved = await client.post(
        f"/api/admin/datasets/records/{record_public_id}/review",
        headers=headers,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    return approved.json()


async def scan_governance(client, headers, entity_public_id, target_use):
    response = await client.post(
        f"/api/admin/data-governance/approvals/dataset_record/{entity_public_id}/{target_use}"
        "/evaluate",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/governed-builds")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/governed-builds", json={"target_pipeline": "rag"}
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_create_get_and_list_build_requests(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/governed-builds",
            headers=headers,
            json={"target_pipeline": "rag", "build_label": "API test build"},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["status"] == "draft"

        fetched = await client.get(f"/api/admin/governed-builds/{body['public_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["build_code"] == body["build_code"]

        listing = await client.get("/api/admin/governed-builds", params={"target_pipeline": "rag"})
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        summary = await client.get("/api/admin/governed-builds/summary")
        assert summary.status_code == 200
        assert "counts_by_status" in summary.json()
    finally:
        await client.aclose()


async def test_full_lifecycle_via_api_creates_a_dataset_version(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        record = await create_approved_record(client, headers, name_suffix="LIFECYCLE")
        await scan_governance(client, headers, record["public_id"], "dataset_export")

        created = await client.post(
            "/api/admin/governed-builds",
            headers=headers,
            json={
                "target_pipeline": "dataset_version",
                "configuration": {"dataset_name": "api-e2e", "dataset_version": "v1"},
            },
        )
        assert created.status_code == 200
        public_id = created.json()["public_id"]

        preflight = await client.post(
            f"/api/admin/governed-builds/{public_id}/preflight", headers=headers
        )
        assert preflight.status_code == 200
        assert preflight.json()["status"] == "preflight_ready"

        confirmed = await client.post(
            f"/api/admin/governed-builds/{public_id}/confirm", headers=headers
        )
        assert confirmed.status_code == 200

        executed = await client.post(
            f"/api/admin/governed-builds/{public_id}/execute", headers=headers
        )
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        version_public_id = executed.json()["result_entity_public_id"]
        assert version_public_id

        manifest_generated = await client.post(
            f"/api/admin/governed-builds/{public_id}/manifest", headers=headers
        )
        assert manifest_generated.status_code == 200
        assert manifest_generated.json()["governance_extension"]["record_count"] == 1

        manifest = await client.get(f"/api/admin/governed-builds/{public_id}/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["governance_extension"]["record_count"] == 1

        history = await client.get(f"/api/admin/governed-builds/{public_id}/history")
        assert history.status_code == 200
        assert len(history.json()["items"]) > 0

        # Data lineage: the dataset_record should be linked to the version.
        lineage = await client.get(
            f"/api/admin/data-lineage/entity/dataset_record/{record['public_id']}"
        )
        assert lineage.status_code == 200
        assert lineage.json()["complete"] is True

        downstream = await client.get(
            f"/api/admin/data-lineage/entity/dataset_record/{record['public_id']}/downstream"
        )
        assert downstream.status_code == 200
        assert any(
            edge["downstream_entity_id"] == version_public_id
            for edge in downstream.json()["items"]
        )
    finally:
        await client.aclose()


async def test_fresh_record_is_blocked_at_preflight_via_api(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await create_approved_record(client, headers, name_suffix="LEGACY")
        created = await client.post(
            "/api/admin/governed-builds",
            headers=headers,
            json={"target_pipeline": "dataset_version"},
        )
        public_id = created.json()["public_id"]
        preflight = await client.post(
            f"/api/admin/governed-builds/{public_id}/preflight", headers=headers
        )
        assert preflight.status_code == 200
        assert preflight.json()["status"] == "blocked"

        blocked = await client.get(f"/api/admin/governed-builds/{public_id}/blocked-items")
        assert blocked.status_code == 200
        assert len(blocked.json()["items"]) >= 1

        cannot_confirm = await client.post(
            f"/api/admin/governed-builds/{public_id}/confirm", headers=headers
        )
        assert cannot_confirm.status_code == 422
    finally:
        await client.aclose()


async def test_cancel_build(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/governed-builds", headers=headers, json={"target_pipeline": "evaluation"}
        )
        public_id = created.json()["public_id"]
        cancelled = await client.post(
            f"/api/admin/governed-builds/{public_id}/cancel", headers=headers
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
    finally:
        await client.aclose()


async def test_lineage_edge_endpoint(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/data-lineage/edges",
            headers=headers,
            json={
                "upstream_entity_type": "manual_data_record",
                "upstream_entity_id": "mdr-api-1",
                "downstream_entity_type": "dataset_record",
                "downstream_entity_id": "ds-api-1",
                "relationship_type": "derived_from",
            },
        )
        assert created.status_code == 200
        upstream = await client.get(
            "/api/admin/data-lineage/entity/dataset_record/ds-api-1/upstream"
        )
        assert upstream.status_code == 200
        assert len(upstream.json()["items"]) == 1
    finally:
        await client.aclose()
