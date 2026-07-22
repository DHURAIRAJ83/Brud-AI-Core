import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.connection import database_connection
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.services.dataset_service import content_hash

pytestmark = pytest.mark.anyio
PASSWORD = "Dataset-Admin-Password-42"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="dataset-admin", display_name="Dataset Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "dataset-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def create_source(client, headers):
    response = await client.post(
        "/api/admin/datasets/sources",
        headers=headers,
        json={"name": "  Tamil   Manual  ", "language": "ta", "source_type": "manual"},
    )
    assert response.status_code == 200
    return response.json()


def instruction(source_id: str, output: str = "வணக்கம்"):
    return {
        "source_public_id": source_id,
        "record_type": "instruction",
        "language": "ta",
        "instruction": "Say hello",
        "output_text": output,
        "metadata": {},
    }


async def test_source_and_record_review_workflow(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        assert (
            await client.post("/api/admin/datasets/sources", json={"name": "x", "language": "ta"})
        ).status_code == 403
        source = await create_source(client, headers)
        assert source["name"] == "Tamil Manual" and "id" not in source
        listing = await client.get("/api/admin/datasets/sources?search=Tamil&page=1&page_size=25")
        assert listing.json()["total"] == 1
        created = await client.post(
            "/api/admin/datasets/records", headers=headers, json=instruction(source["public_id"])
        )
        assert created.status_code == 200
        record = created.json()
        assert "id" not in record and record["status"] == "draft"
        duplicate = await client.post(
            "/api/admin/datasets/records", headers=headers, json=instruction(source["public_id"])
        )
        assert duplicate.status_code == 409 and record["public_id"] in duplicate.text
        submitted = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/submit", headers=headers
        )
        assert submitted.json()["status"] == "pending_review"
        approved = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/review",
            headers=headers,
            json={"decision": "approve"},
        )
        assert approved.json()["status"] == "approved"
        edit = await client.patch(
            f"/api/admin/datasets/records/{record['public_id']}",
            headers=headers,
            json={"output_text": "changed"},
        )
        assert edit.status_code == 422
        archived = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/archive", headers=headers
        )
        assert archived.json()["status"] == "archived"
        restored = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/restore", headers=headers
        )
        assert restored.json()["status"] == "draft"
        reviews = await client.get(f"/api/admin/datasets/records/{record['public_id']}/reviews")
        assert len(reviews.json()["items"]) == 4
        stats = (await client.get("/api/admin/datasets/statistics")).json()
        assert stats["total_sources"] == 1 and stats["total_records"] == 1
        assert stats["duplicate_conflicts"] == 1
        assert (await client.get("/api/admin/datasets/duplicates")).json()["items"]
        payloads = json.dumps([source, record, stats])
        assert (
            "password_hash" not in payloads
            and "token_hash" not in payloads
            and "/tmp/" not in payloads
        )
    finally:
        await client.aclose()
    with database_connection(api_app.state.settings.resolved_database_path) as connection:
        events = {row[0] for row in connection.execute("SELECT event_type FROM audit_logs")}
    assert {
        "dataset_source_created",
        "dataset_record_created",
        "dataset_record_approved",
        "dataset_duplicate_rejected",
    } <= events


@pytest.mark.parametrize(
    ("record_type", "fields"),
    [
        ("pretrain", {"input_text": "content"}),
        ("instruction", {"instruction": "Do", "output_text": "Done"}),
        ("chat", {"input_text": "Hi", "output_text": "Hello"}),
        (
            "translation",
            {
                "input_text": "Hello",
                "output_text": "வணக்கம்",
                "metadata": {"source_language": "en", "target_language": "ta"},
            },
        ),
        (
            "tanglish_pair",
            {"input_text": "vanakkam", "normalized_input": "வணக்கம்", "output_text": "வணக்கம்"},
        ),
        ("safety", {"input_text": "unsafe", "output_text": "refuse"}),
        ("preference", {"input_text": "prompt", "output_text": "chosen"}),
    ],
)
async def test_each_record_type(api_app: FastAPI, record_type: str, fields: dict) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        payload = {
            "source_public_id": source["public_id"],
            "record_type": record_type,
            "language": "mixed",
            "metadata": {},
            **fields,
        }
        assert (
            await client.post("/api/admin/datasets/records", headers=headers, json=payload)
        ).status_code == 200
    finally:
        await client.aclose()


async def test_validation_rejection_and_request_changes(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        invalid_source = await client.post(
            "/api/admin/datasets/sources",
            headers=headers,
            json={"name": "Import", "language": "ta", "source_type": "json"},
        )
        assert invalid_source.status_code == 422
        assert (await client.get("/api/admin/datasets/sources?page_size=101")).status_code == 422
        assert (
            await client.get(f"/api/admin/datasets/records?search={'x' * 201}")
        ).status_code == 422
        source = await create_source(client, headers)
        invalid_record = {**instruction(source["public_id"]), "output_text": None}
        assert (
            await client.post("/api/admin/datasets/records", headers=headers, json=invalid_record)
        ).status_code == 422
        record = (
            await client.post(
                "/api/admin/datasets/records",
                headers=headers,
                json=instruction(source["public_id"], "unique"),
            )
        ).json()
        await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/submit", headers=headers
        )
        missing_comment = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/review",
            headers=headers,
            json={"decision": "reject"},
        )
        assert missing_comment.status_code == 422
        rejected = await client.post(
            f"/api/admin/datasets/records/{record['public_id']}/review",
            headers=headers,
            json={"decision": "reject", "comments": "Needs a more natural answer."},
        )
        assert rejected.json()["status"] == "rejected"
    finally:
        await client.aclose()


def test_content_hash_is_deterministic_and_tamil_preserving() -> None:
    first = {
        "record_type": "instruction",
        "language": "ta",
        "instruction": "வணக்கம்  உலகம்",
        "input_text": None,
        "output_text": " பதில் ",
        "normalized_input": None,
    }
    second = {**first, "instruction": "வணக்கம் உலகம்", "output_text": "பதில்"}
    assert content_hash(first) == content_hash(second)
