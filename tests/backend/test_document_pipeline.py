
import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.connection import database_connection
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate
from backend.services.document_service import clean_document_text, safe_filename

pytestmark = pytest.mark.anyio
PASSWORD = "Document-Pipeline-Password-42"


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
        AdminCreate(username="document-admin", display_name="Document Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login", json={"username": "document-admin", "password": PASSWORD}
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def upload(client, headers, content: bytes, filename: str = "sample.pdf"):
    return await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": (filename, content, "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )


async def test_document_workflow_security_review_segmentation_and_import(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    content = make_pdf("First English paragraph for Brud AI.", "Second page paragraph.")
    try:
        unauth = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
        assert (await unauth.get("/api/admin/documents")).status_code == 401
        await unauth.aclose()
        assert (await upload(client, {}, content)).status_code == 403
        capabilities = (await client.get("/api/admin/documents/capabilities")).json()
        assert capabilities["pdf_extraction"] is True
        assert "tam" in capabilities["ocr_languages"] and "eng" in capabilities["ocr_languages"]
        response = await upload(client, headers, content, "../sample.pdf")
        assert response.status_code == 200
        document = response.json()
        assert document["original_filename"] == "sample.pdf"
        assert "stored_filename" not in document and "/tmp/" not in response.text
        public_id = document["public_id"]
        duplicate = await upload(client, headers, content)
        assert duplicate.status_code == 409 and public_id in duplicate.text
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0] == 0
        analyzed = await client.post(f"/api/admin/documents/{public_id}/analyze", headers=headers)
        assert analyzed.status_code == 200
        processed = await client.post(
            f"/api/admin/documents/{public_id}/process",
            headers=headers,
            json={"strategy": "embedded_text"},
        )
        assert processed.status_code == 200
        pages = (await client.get(f"/api/admin/documents/{public_id}/pages")).json()
        assert pages["total"] == 2 and all("raw_text" not in item for item in pages["items"])
        detail = (await client.get(f"/api/admin/documents/{public_id}/pages/1")).json()
        raw = detail["raw_text"]
        edited = await client.patch(
            f"/api/admin/documents/{public_id}/pages/1",
            headers=headers,
            json={"cleaned_text": "Edited cleaned text only."},
        )
        assert edited.status_code == 200 and edited.json()["raw_text"] == raw
        segmented = await client.post(
            f"/api/admin/documents/{public_id}/segment",
            headers=headers,
            json={"mode": "page_as_pretrain", "language": "en"},
        )
        assert segmented.status_code == 200
        candidates = (await client.get(f"/api/admin/documents/{public_id}/candidates")).json()
        assert candidates["total"] == 2
        candidate_id = candidates["items"][0]["public_id"]
        assert (
            await client.post(
                f"/api/admin/documents/{public_id}/candidates/{candidate_id}/select",
                headers=headers,
            )
        ).status_code == 200
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0] == 0
        imported = await client.post(
            f"/api/admin/documents/{public_id}/candidates/import",
            headers=headers,
            json={"confirm": True},
        )
        assert imported.status_code == 200 and imported.json()["imported"] == 1
        retry = await client.post(
            f"/api/admin/documents/{public_id}/candidates/import",
            headers=headers,
            json={"confirm": True},
        )
        assert retry.status_code == 200 and retry.json()["imported"] == 0
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            record = connection.execute(
                "SELECT status,metadata_json FROM dataset_records"
            ).fetchone()
            assert record["status"] == "draft" and public_id in record["metadata_json"]
            assert (
                connection.execute("SELECT COUNT(*) FROM document_page_revisions").fetchone()[0]
                == 1
            )
            events = connection.execute(
                "SELECT COUNT(*) FROM document_processing_events"
            ).fetchone()[0]
            audits = connection.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE resource_type='document'"
            ).fetchone()[0]
            assert events >= 8 and audits >= 6
        jobs = (await client.get(f"/api/admin/documents/{public_id}/jobs")).json()
        job_id = jobs["items"][0]["public_id"]
        assert (await client.get(f"/api/admin/documents/jobs/{job_id}/events")).status_code == 200
        report = await client.get(f"/api/admin/documents/{public_id}/report")
        assert report.status_code == 200 and "text/csv" in report.headers["content-type"]
        assert "stored_filename" not in report.text and "/tmp/" not in report.text
    finally:
        await client.aclose()


@pytest.mark.parametrize("name", ["../safe.pdf", "..\\safe.pdf"])
def test_filename_is_sanitized(name: str) -> None:
    assert safe_filename(name) == "safe.pdf"


def test_cleaning_preserves_tamil_and_raw_evidence() -> None:
    raw = "  வணக்கம்\u200b\r\n\r\n\r\n தமிழ்  \ufffd "
    result = clean_document_text(raw)
    assert "வணக்கம்" in result["cleaned"] and "தமிழ்" in result["cleaned"]
    assert raw.endswith("\ufffd ")
    assert {item["code"] for item in result["warnings"]} >= {"replacement_character"}


async def test_invalid_pdf_controls(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        assert (await upload(client, headers, b"not a pdf")).status_code == 422
        assert (await upload(client, headers, b"", "empty.pdf")).status_code == 422
        assert (await upload(client, headers, make_pdf("x"), "bad.txt")).status_code == 422
        assert not any((api_app.state.settings.resolved_document_dir / "pending").glob("*"))
    finally:
        await client.aclose()
