import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Document-SFT-Workflow-Password-42"


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
        AdminCreate(username="sft-workflow-admin", display_name="SFT Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login", json={"username": "sft-workflow-admin", "password": PASSWORD}
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def _document_with_approved_verified_chunk(client, headers, *, code="SRC-SFT-API-0001"):
    upload = await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": ("sample.pdf", make_pdf("Paragraph one content here."), "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )
    assert upload.status_code == 200
    document_id = upload.json()["public_id"]
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/process",
            headers=headers,
            json={"strategy": "embedded_text"},
        )
    ).status_code == 200

    source = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={"source_code": code, "title": "Test source", "source_type": "document_derived"},
    )
    assert source.status_code == 200
    source_id = source.json()["public_id"]
    assert (
        await client.put(
            f"/api/admin/data-sources/{source_id}/rights",
            headers=headers,
            json={"rights_status": "public_domain", "training_use_allowed": True},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/source-link",
            headers=headers,
            json={"source_public_id": source_id},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/pages/1/approve",
            headers=headers,
            json={},
        )
    ).status_code == 200

    generated = await client.post(
        f"/api/admin/semantic-chunks/document/{document_id}/generate", headers=headers, json={}
    )
    assert generated.status_code == 200
    chunk_id = generated.json()["chunk_public_ids"][0]
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/classify",
            headers=headers,
            json={"chunk_type": "definition"},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={}
        )
    ).status_code == 200
    return document_id


async def test_tamil_quality_and_sft_endpoints_require_auth(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_id = await _document_with_approved_verified_chunk(client, headers)
        unauth = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
        assert (
            await unauth.post(f"/api/admin/documents/{document_id}/tamil-quality/detect")
        ).status_code == 401
        assert (
            await unauth.get(f"/api/admin/documents/{document_id}/sft-candidates")
        ).status_code == 401
        await unauth.aclose()
    finally:
        await client.aclose()


async def test_sft_candidate_generation_review_and_export_end_to_end(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_id = await _document_with_approved_verified_chunk(client, headers)

        no_csrf = await client.post(f"/api/admin/documents/{document_id}/sft-candidates/generate")
        assert no_csrf.status_code == 403

        generated = await client.post(
            f"/api/admin/documents/{document_id}/sft-candidates/generate",
            headers=headers,
            json={},
        )
        assert generated.status_code == 200
        candidates = generated.json()["items"]
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["task"] == "definition"
        assert candidate["rights_status"] == "verified"

        reviewed = await client.post(
            f"/api/admin/documents/{document_id}/sft-candidates/{candidate['public_id']}/review",
            headers=headers,
            json={"action": "approve"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["items"][0]["quality_status"] == "approved"

        exported = await client.post(
            f"/api/admin/documents/{document_id}/sft-export",
            headers=headers,
            json={"confirm": True},
        )
        assert exported.status_code == 200
        export_body = exported.json()
        assert export_body["record_count"] == 1
        assert export_body["checksum_sha256"]

        fetched = await client.get(
            f"/api/admin/documents/{document_id}/sft-export/{export_body['public_id']}"
        )
        assert fetched.status_code == 200
        assert fetched.json()["checksum_sha256"] == export_body["checksum_sha256"]
    finally:
        await client.aclose()


async def test_tamil_quality_detect_and_list_via_api(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        document_id = await _document_with_approved_verified_chunk(client, headers)
        detected = await client.post(
            f"/api/admin/documents/{document_id}/tamil-quality/detect", headers=headers
        )
        assert detected.status_code == 200
        listed = await client.get(f"/api/admin/documents/{document_id}/tamil-quality")
        assert listed.status_code == 200
        summary = await client.get(f"/api/admin/documents/{document_id}/tamil-quality/summary")
        assert summary.status_code == 200
        assert summary.json()["document_public_id"] == document_id
    finally:
        await client.aclose()
