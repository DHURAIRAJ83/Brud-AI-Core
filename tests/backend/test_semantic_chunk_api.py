import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Semantic-Chunk-Password-42"


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
        AdminCreate(username="chunk-admin", display_name="Chunk Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login", json={"username": "chunk-admin", "password": PASSWORD}
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def create_source(client, headers, *, code="SRC-CHUNK-API-0001"):
    response = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={"source_code": code, "title": "Test source", "source_type": "document_derived"},
    )
    assert response.status_code == 200
    return response.json()


async def ready_document(client, headers, *, source_code="SRC-CHUNK-API-0001"):
    upload = await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": ("sample.pdf", make_pdf("Placeholder text."), "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )
    assert upload.status_code == 200
    document_public_id = upload.json()["public_id"]
    processed = await client.post(
        f"/api/admin/documents/{document_public_id}/process",
        headers=headers,
        json={"strategy": "embedded_text"},
    )
    assert processed.status_code == 200
    edited = await client.patch(
        f"/api/admin/documents/{document_public_id}/pages/1",
        headers=headers,
        json={"cleaned_text": "First paragraph here.\n\nSecond paragraph here."},
    )
    assert edited.status_code == 200
    source = await create_source(client, headers, code=source_code)
    linked = await client.post(
        f"/api/admin/documents/{document_public_id}/source-link",
        headers=headers,
        json={"source_public_id": source["public_id"]},
    )
    assert linked.status_code == 200
    approved = await client.post(
        f"/api/admin/documents/{document_public_id}/pages/1/approve", headers=headers, json={}
    )
    assert approved.status_code == 200
    return document_public_id, source


async def test_endpoints_require_authentication(api_app: FastAPI) -> None:
    unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await unauthenticated.get(
            "/api/admin/semantic-chunks/document/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401
    finally:
        await unauthenticated.aclose()


async def test_mutation_requires_csrf_token(api_app: FastAPI) -> None:
    client, _headers = await client_and_csrf(api_app)
    try:
        response = await client.post(
            "/api/admin/semantic-chunks/document/00000000-0000-0000-0000-000000000000/generate"
        )
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_generate_requires_a_linked_source_returns_422(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
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
        response = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_generate_list_and_full_chunk_lifecycle(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(client, headers)
        generated = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        assert generated.status_code == 200
        body = generated.json()
        assert body["generated_chunk_count"] == 2

        listing = await client.get(
            f"/api/admin/semantic-chunks/document/{document_public_id}", headers=headers
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 2

        chunk_id = body["chunk_public_ids"][0]
        detail = await client.get(f"/api/admin/semantic-chunks/{chunk_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["chunk_type"] == "paragraph"

        classified = await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/classify",
            headers=headers,
            json={"chunk_type": "heading"},
        )
        assert classified.status_code == 200
        assert classified.json()["chunk_type"] == "heading"

        submitted = await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
        )
        assert submitted.status_code == 200
        approved = await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={}
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        history = await client.get(
            f"/api/admin/semantic-chunks/{chunk_id}/history", headers=headers
        )
        assert history.status_code == 200
        assert len(history.json()["events"]) >= 1

        quality = await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/quality-check", headers=headers
        )
        assert quality.status_code == 200
        assert "blocking_issues" in quality.json()
    finally:
        await client.aclose()


async def test_split_an_approved_chunk_returns_422(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(
            client, headers, source_code="SRC-CHUNK-API-SPLIT"
        )
        generated = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        chunk_id = generated.json()["chunk_public_ids"][0]
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
        )
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={}
        )
        response = await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/split", headers=headers, json={"split_at": 3}
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_edit_text_reopens_an_approved_chunk(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(
            client, headers, source_code="SRC-CHUNK-API-EDIT"
        )
        generated = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        chunk_id = generated.json()["chunk_public_ids"][0]
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
        )
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={}
        )
        edited = await client.patch(
            f"/api/admin/semantic-chunks/{chunk_id}",
            headers=headers,
            json={"text": "Corrected paragraph text.", "change_summary": "fixed a typo"},
        )
        assert edited.status_code == 200
        assert edited.json()["status"] == "needs_review"
    finally:
        await client.aclose()


async def test_merge_two_generated_chunks(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(
            client, headers, source_code="SRC-CHUNK-API-MERGE"
        )
        generated = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        first_id, second_id = generated.json()["chunk_public_ids"]
        merged = await client.post(
            f"/api/admin/semantic-chunks/{first_id}/merge",
            headers=headers,
            json={"other_chunk_public_id": second_id},
        )
        assert merged.status_code == 200
        excluded = await client.get(
            f"/api/admin/semantic-chunks/{second_id}", headers=headers
        )
        assert excluded.json()["status"] == "excluded"
    finally:
        await client.aclose()


async def test_assign_parent_cycle_returns_422(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(
            client, headers, source_code="SRC-CHUNK-API-HIER"
        )
        generated = await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        parent_id, child_id = generated.json()["chunk_public_ids"]
        assigned = await client.post(
            f"/api/admin/semantic-chunks/{child_id}/assign-parent",
            headers=headers,
            json={"parent_chunk_public_id": parent_id},
        )
        assert assigned.status_code == 200
        cycle = await client.post(
            f"/api/admin/semantic-chunks/{parent_id}/assign-parent",
            headers=headers,
            json={"parent_chunk_public_id": child_id},
        )
        assert cycle.status_code == 422
    finally:
        await client.aclose()


async def test_coverage_report_endpoint(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_public_id, _source = await ready_document(
            client, headers, source_code="SRC-CHUNK-API-COVERAGE"
        )
        await client.post(
            f"/api/admin/semantic-chunks/document/{document_public_id}/generate", headers=headers
        )
        response = await client.get(
            f"/api/admin/semantic-chunks/document/{document_public_id}/coverage", headers=headers
        )
        assert response.status_code == 200
        assert "1" in response.json()
    finally:
        await client.aclose()
