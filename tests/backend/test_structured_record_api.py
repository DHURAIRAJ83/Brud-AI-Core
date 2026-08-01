import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Structured-Record-Password-42"


def make_pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


async def client_and_csrf(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="record-admin", display_name="Record Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login", json={"username": "record-admin", "password": PASSWORD}
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def approved_chunk(client, headers, *, source_code="SRC-RECORD-API-0001"):
    upload = await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": ("sample.pdf", make_pdf("Placeholder text."), "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )
    document_public_id = upload.json()["public_id"]
    await client.post(
        f"/api/admin/documents/{document_public_id}/process",
        headers=headers,
        json={"strategy": "embedded_text"},
    )
    await client.patch(
        f"/api/admin/documents/{document_public_id}/pages/1",
        headers=headers,
        json={"cleaned_text": "வணக்கம் தமிழ்."},
    )
    source = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={
            "source_code": source_code,
            "title": "Test source",
            "source_type": "document_derived",
        },
    )
    source_public_id = source.json()["public_id"]
    await client.post(
        f"/api/admin/documents/{document_public_id}/source-link",
        headers=headers,
        json={"source_public_id": source_public_id},
    )
    await client.post(
        f"/api/admin/documents/{document_public_id}/pages/1/approve", headers=headers, json={}
    )
    generated = await client.post(
        f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
    )
    chunk_id = generated.json()["chunk_public_ids"][0]
    await client.post(
        f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
    )
    await client.post(f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={})
    return chunk_id, source_public_id


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get("/api/admin/structured-records")
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, _headers = await client_and_csrf(api_app)
    try:
        response = await client.post(
            "/api/admin/structured-records/from-chunks",
            json={"record_type": "plain_text", "chunk_public_ids": ["x"], "fields": {}},
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_create_review_and_export_dictionary_entry(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        chunk_id, _source = await approved_chunk(client, headers)
        created = await client.post(
            "/api/admin/structured-records/from-chunks",
            headers=headers,
            json={
                "record_type": "dictionary_entry",
                "chunk_public_ids": [chunk_id],
                "fields": {"word": "வணக்கம்", "meanings_json": '["hello", "greeting"]'},
            },
        )
        assert created.status_code == 200
        candidate = created.json()
        assert candidate["status"] == "draft"
        candidate_id = candidate["public_id"]

        listing = await client.get("/api/admin/structured-records", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        submitted = await client.post(
            f"/api/admin/structured-records/{candidate_id}/submit-review", headers=headers
        )
        assert submitted.status_code == 200
        approved = await client.post(
            f"/api/admin/structured-records/{candidate_id}/approve", headers=headers
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        history = await client.get(
            f"/api/admin/structured-records/{candidate_id}/history", headers=headers
        )
        assert history.status_code == 200

        usage = await client.post(
            f"/api/admin/structured-records/{candidate_id}/usage-check",
            headers=headers,
            json={"target_use": "training"},
        )
        assert usage.status_code == 200
        assert usage.json()["allowed"] is False  # no rights declared on the source

        exported = await client.post(
            f"/api/admin/structured-records/{candidate_id}/export-dataset", headers=headers
        )
        assert exported.status_code == 200
        assert exported.json()["exported_dataset_record_public_id"] is not None

        duplicate_export = await client.post(
            f"/api/admin/structured-records/{candidate_id}/export-dataset", headers=headers
        )
        assert duplicate_export.status_code == 409
    finally:
        await client.aclose()


async def test_rag_chunk_export_is_blocked_and_handoff_works(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        chunk_id, _source = await approved_chunk(client, headers, source_code="SRC-RECORD-API-RAG")
        created = await client.post(
            "/api/admin/structured-records/from-chunks",
            headers=headers,
            json={
                "record_type": "rag_chunk",
                "chunk_public_ids": [chunk_id],
                "fields": {"text": "வணக்கம் தமிழ்."},
            },
        )
        candidate_id = created.json()["public_id"]
        await client.post(
            f"/api/admin/structured-records/{candidate_id}/submit-review", headers=headers
        )
        await client.post(f"/api/admin/structured-records/{candidate_id}/approve", headers=headers)

        blocked = await client.post(
            f"/api/admin/structured-records/{candidate_id}/export-dataset", headers=headers
        )
        assert blocked.status_code == 422

        handoff = await client.post(
            f"/api/admin/structured-records/{candidate_id}/create-rag-candidate", headers=headers
        )
        assert handoff.status_code == 200
        assert handoff.json()["rag_handoff_at"] is not None
    finally:
        await client.aclose()


async def test_conflict_check_flags_alternate_dictionary_sense(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        chunk_id, _source = await approved_chunk(
            client, headers, source_code="SRC-RECORD-API-CONFLICT"
        )
        first = await client.post(
            "/api/admin/structured-records/from-chunks",
            headers=headers,
            json={
                "record_type": "dictionary_entry",
                "chunk_public_ids": [chunk_id],
                "fields": {"word": "vanakkam", "meanings_json": '["hello"]'},
            },
        )
        first_id = first.json()["public_id"]
        await client.post(
            f"/api/admin/structured-records/{first_id}/submit-review", headers=headers
        )
        await client.post(f"/api/admin/structured-records/{first_id}/approve", headers=headers)

        second = await client.post(
            "/api/admin/structured-records/from-chunks",
            headers=headers,
            json={
                "record_type": "dictionary_entry",
                "chunk_public_ids": [chunk_id],
                "fields": {"word": "vanakkam", "meanings_json": '["a respectful greeting"]'},
            },
        )
        second_id = second.json()["public_id"]
        conflict = await client.post(
            f"/api/admin/structured-records/{second_id}/conflict-check", headers=headers
        )
        assert conflict.status_code == 200
        assert conflict.json()["conflict"]["type"] == "alternate_sense"
    finally:
        await client.aclose()
