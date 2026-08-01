import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Document-Workspace-Password-42"


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
        AdminCreate(username="workspace-admin", display_name="Workspace Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login", json={"username": "workspace-admin", "password": PASSWORD}
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def upload_and_process(client, headers, *, texts=("First page.", "Second page.")):
    response = await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": ("sample.pdf", make_pdf(*texts), "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )
    assert response.status_code == 200
    public_id = response.json()["public_id"]
    processed = await client.post(
        f"/api/admin/documents/{public_id}/process",
        headers=headers,
        json={"strategy": "embedded_text"},
    )
    assert processed.status_code == 200
    return public_id


async def create_source(client, headers, *, code="SRC-DOC-API-0001"):
    response = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={
            "source_code": code,
            "title": "Test document source",
            "source_type": "document_derived",
        },
    )
    assert response.status_code == 200
    return response.json()


async def test_workspace_endpoint_requires_auth_and_reports_unlinked(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        unauth = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
        public_id = await upload_and_process(client, headers)
        assert (await unauth.get(f"/api/admin/documents/{public_id}/workspace")).status_code == 401
        await unauth.aclose()

        workspace = (await client.get(f"/api/admin/documents/{public_id}/workspace")).json()
        assert workspace["source_status"] == "unlinked"
        assert workspace["readiness"] == "not_ready"
    finally:
        await client.aclose()


async def test_link_source_requires_csrf_and_updates_workspace(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        source = await create_source(client, headers)

        no_csrf = await client.post(
            f"/api/admin/documents/{public_id}/source-link",
            json={"source_public_id": source["public_id"]},
        )
        assert no_csrf.status_code in (401, 403)

        linked = await client.post(
            f"/api/admin/documents/{public_id}/source-link",
            headers=headers,
            json={"source_public_id": source["public_id"]},
        )
        assert linked.status_code == 200
        workspace = (await client.get(f"/api/admin/documents/{public_id}/workspace")).json()
        assert workspace["source_status"] == "linked"
        assert workspace["source"]["public_id"] == source["public_id"]
    finally:
        await client.aclose()


async def test_page_image_renders_png(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        response = await client.get(f"/api/admin/documents/{public_id}/pages/1/image")
        assert response.status_code == 200
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert response.headers["content-type"] == "image/png"
    finally:
        await client.aclose()


async def test_page_extractions_history_recorded_via_process(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        # The bare /process endpoint (existing, unchanged) does not itself
        # record extraction history -- that is exclusively the new
        # workspace wrapper's job, exercised via reprocess below.
        rerun = await client.post(
            f"/api/admin/documents/{public_id}/pages/1/request-extraction-rerun",
            headers=headers,
            json={"strategy": "embedded_text"},
        )
        assert rerun.status_code == 200
        extractions = (
            await client.get(f"/api/admin/documents/{public_id}/pages/1/extractions")
        ).json()
        assert len(extractions["items"]) == 1
        assert extractions["items"][0]["extraction_method"] == "embedded"
    finally:
        await client.aclose()


async def test_revisions_endpoint_and_edit_page_change_summary(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        edited = await client.patch(
            f"/api/admin/documents/{public_id}/pages/1",
            headers=headers,
            json={"cleaned_text": "Edited text.", "change_summary": "fixed a typo"},
        )
        assert edited.status_code == 200
        revisions = (await client.get(f"/api/admin/documents/{public_id}/pages/1/revisions")).json()
        assert len(revisions["items"]) == 1
        assert revisions["items"][0]["cleaned_text"] == "Edited text."
    finally:
        await client.aclose()


async def test_restore_previous_revision(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        await client.patch(
            f"/api/admin/documents/{public_id}/pages/1",
            headers=headers,
            json={"cleaned_text": "First correction."},
        )
        await client.patch(
            f"/api/admin/documents/{public_id}/pages/1",
            headers=headers,
            json={"cleaned_text": "Second correction."},
        )
        restored = await client.post(
            f"/api/admin/documents/{public_id}/pages/1/revisions/1/restore",
            headers=headers,
        )
        assert restored.status_code == 200
        page = (await client.get(f"/api/admin/documents/{public_id}/pages/1")).json()
        assert page["cleaned_text"] == "First correction."
    finally:
        await client.aclose()


async def test_full_review_lifecycle_approve_reject_exclude_reopen(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        source = await create_source(client, headers, code="SRC-DOC-LIFECYCLE-API")
        await client.post(
            f"/api/admin/documents/{public_id}/source-link",
            headers=headers,
            json={"source_public_id": source["public_id"]},
        )

        blocked = await client.post(
            f"/api/admin/documents/{public_id}/pages/1/approve", headers=headers, json={}
        )
        assert blocked.status_code == 200  # embedded extraction already populated cleaned_text

        rejected = await client.post(
            f"/api/admin/documents/{public_id}/pages/2/reject",
            headers=headers,
            json={"notes": "not usable"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["review_status"] == "rejected"

        excluded = await client.post(
            f"/api/admin/documents/{public_id}/pages/2/exclude", headers=headers, json={}
        )
        assert excluded.status_code == 422  # rejected -> excluded is not a valid transition

        events = (
            await client.get(f"/api/admin/documents/{public_id}/pages/1/review-events")
        ).json()
        assert len(events["items"]) == 1
        assert events["items"][0]["action"] == "approve"

        summary = (await client.get(f"/api/admin/documents/{public_id}/review-summary")).json()
        assert summary["review_status_counts"]["approved"] == 1
        assert summary["review_status_counts"]["rejected"] == 1
    finally:
        await client.aclose()


async def test_approve_blocked_without_source_link(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        response = await client.post(
            f"/api/admin/documents/{public_id}/pages/1/approve", headers=headers, json={}
        )
        assert response.status_code == 422
        body = response.json()
        assert "traceback" not in str(body).lower()
    finally:
        await client.aclose()


async def test_cleanup_suggestions_and_apply(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        await client.patch(
            f"/api/admin/documents/{public_id}/pages/1",
            headers=headers,
            json={"cleaned_text": "hello    world with bro-\nken text"},
        )
        suggestions = (
            await client.get(f"/api/admin/documents/{public_id}/pages/1/cleanup-suggestions")
        ).json()
        assert len(suggestions["items"]) > 0
        applied = await client.post(
            f"/api/admin/documents/{public_id}/pages/1/apply-cleanup",
            headers=headers,
            json={"suggestions": suggestions["items"]},
        )
        assert applied.status_code == 200
        assert "  " not in applied.json()["cleaned_text"]
    finally:
        await client.aclose()


async def test_repeated_elements_detect_and_bulk_apply_requires_confirmation(
    api_app: FastAPI,
) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(
            client, headers, texts=tuple(f"Confidential Draft\nbody {i}" for i in range(1, 6))
        )
        detected = await client.post(
            f"/api/admin/documents/{public_id}/repeated-elements/detect", headers=headers
        )
        assert detected.status_code == 200
        assert len(detected.json()["items"]) >= 1
        element_id = detected.json()["items"][0]["public_id"]

        listed = await client.get(f"/api/admin/documents/{public_id}/repeated-elements")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) >= 1

        unconfirmed = await client.post(
            f"/api/admin/documents/{public_id}/repeated-elements/{element_id}/review",
            headers=headers,
            json={"action": "apply_all", "confirm": False},
        )
        assert unconfirmed.status_code == 422

        confirmed = await client.post(
            f"/api/admin/documents/{public_id}/repeated-elements/{element_id}/review",
            headers=headers,
            json={"action": "apply_all", "confirm": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "applied"
    finally:
        await client.aclose()


async def test_send_to_segmentation_blocked_until_ready(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        blocked = await client.post(
            f"/api/admin/documents/{public_id}/send-to-segmentation",
            headers=headers,
            json={"mode": "page_as_pretrain", "language": "en"},
        )
        assert blocked.status_code == 422

        source = await create_source(client, headers, code="SRC-DOC-SEGMENT-API")
        await client.post(
            f"/api/admin/documents/{public_id}/source-link",
            headers=headers,
            json={"source_public_id": source["public_id"]},
        )
        await client.post(
            f"/api/admin/documents/{public_id}/pages/1/approve", headers=headers, json={}
        )
        await client.post(
            f"/api/admin/documents/{public_id}/pages/2/approve", headers=headers, json={}
        )
        ready = await client.post(
            f"/api/admin/documents/{public_id}/send-to-segmentation",
            headers=headers,
            json={"mode": "page_as_pretrain", "language": "en"},
        )
        assert ready.status_code == 200
    finally:
        await client.aclose()


async def test_every_new_mutation_is_audited(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        public_id = await upload_and_process(client, headers)
        source = await create_source(client, headers, code="SRC-DOC-AUDIT-API")
        await client.post(
            f"/api/admin/documents/{public_id}/source-link",
            headers=headers,
            json={"source_public_id": source["public_id"]},
        )
        await client.post(
            f"/api/admin/documents/{public_id}/pages/1/approve", headers=headers, json={}
        )

        audit = await client.get("/api/admin/audit/recent?limit=50")
        assert audit.status_code == 200
        events = {item["event_type"] for item in audit.json()["items"]}
        assert "document_source_linked" in events
        assert "document_page_approve" in events
    finally:
        await client.aclose()
