import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.auth import AdminCreate
from backend.services.dataset_sample_quarantine_service import ExternalDatasetQuarantineService

pytestmark = pytest.mark.anyio
PASSWORD = "Sample-Import-Admin-Password-42"
BASE = "/api/admin/dataset-sample-imports"
ADMIN_USERNAME = "sample-import-admin"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=ADMIN_USERNAME, display_name="Sample Import Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


def _finalized_case(app: FastAPI) -> dict:
    settings = app.state.settings
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": "system"}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Corpus", "normalized_name": "corpus"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": "system",
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    for permission_type in ("rag_use", "evaluation_use"):
        verification.assess_permission(
            case["public_id"], permission_type,
            {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
        )
        verification.review_permission(
            case["public_id"], permission_type,
            status="approved", reviewed_by="system", reason="ok",
        )
    return verification.lock_case(case["public_id"], {"summary": "done"})


async def _create_sample_import(
    client, headers, case_public_id: str, candidate_public_id: str
) -> dict:
    response = await client.post(
        BASE + "/sample-imports",
        headers=headers,
        json={
            "verification_case_public_id": case_public_id,
            "candidate_public_id": candidate_public_id,
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 100,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_list_sample_imports_requires_authentication(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(BASE + "/sample-imports")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_create_sample_import_requires_csrf(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            BASE + "/sample-imports",
            json={
                "verification_case_public_id": case["public_id"],
                "candidate_public_id": case["candidate_public_id"],
                "purpose": "manual_review",
                "selection_method": "deterministic_first_n",
            },
        )
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_create_sample_import_rejects_prohibited_purpose(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            BASE + "/sample-imports",
            headers=headers,
            json={
                "verification_case_public_id": case["public_id"],
                "candidate_public_id": case["candidate_public_id"],
                "purpose": "training",
                "selection_method": "deterministic_first_n",
            },
        )
        assert response.status_code >= 400
    finally:
        await client.aclose()


async def test_create_sample_import_rejects_unfinalized_case(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "s2", "requested_by_admin_public_id": "system"}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "X", "normalized_name": "x"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-unfinalized",
            "requested_by_admin_public_id": "system",
        }
    )
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            BASE + "/sample-imports",
            headers=headers,
            json={
                "verification_case_public_id": case["public_id"],
                "candidate_public_id": candidate["public_id"],
                "purpose": "manual_review",
                "selection_method": "deterministic_first_n",
            },
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_full_golden_path_through_finalize_and_report(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        sample_import = await _create_sample_import(
            client, headers, case["public_id"], case["candidate_public_id"]
        )
        assert sample_import["status"] == "draft"

        approval_request = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/request-approval",
            headers=headers,
            json={
                "purpose": "manual_review",
                "requested_record_limit": 500,
                "requested_byte_limit": 1_000_000,
            },
        )
        assert approval_request.status_code == 200, approval_request.text
        assert approval_request.json()["status"] == "pending"

        approved = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/approve",
            headers=headers,
            json={
                "approved_record_limit": 500,
                "approved_byte_limit": 1_000_000,
                "expires_at": "2026-12-31T00:00:00",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        # Seed a downloaded file directly (the download endpoint needs
        # real network -- covered separately by unit tests of the
        # download service/transport) so the rest of the pipeline can
        # be exercised end-to-end through the real HTTP routes.
        settings = api_app.state.settings
        quarantine = ExternalDatasetQuarantineService(settings)
        quarantine.ensure_layout(sample_import["public_id"])
        text_path = quarantine.original_file_path(sample_import["public_id"], "sample.txt")
        text_path.write_bytes(b"hello world, this is a clean training example.")
        samples = DatasetSampleImportRepository(settings.resolved_database_path)
        samples.add_file(
            sample_import["public_id"],
            {
                "original_filename": "sample.txt",
                "safe_filename": "sample.txt",
                "relative_path": "sample.txt",
            },
        )

        validated = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/validate-files",
            headers=headers,
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["items"][0]["status"] == "safe_for_scan"

        scanned = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/scan", headers=headers
        )
        assert scanned.status_code == 200, scanned.text
        assert scanned.json()["items"][0]["verdict"] == "clean_by_policy"

        parsed = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/parse", headers=headers
        )
        assert parsed.status_code == 200, parsed.text
        records = parsed.json()["items"]
        assert len(records) == 1

        quality = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/run-quality-checks",
            headers=headers,
        )
        assert quality.status_code == 200

        record_id = records[0]["public_id"]
        review = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/records/{record_id}/review",
            headers=headers,
            json={"decision": "accept", "reason": "Looks fine on manual inspection"},
        )
        assert review.status_code == 200, review.text

        finalized = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/finalize", headers=headers
        )
        assert finalized.status_code == 200, finalized.text
        body = finalized.json()
        assert body["locked_at"] is not None
        assert body["rag_sandbox_eligible"] is True
        assert "training_approved" not in str(body)

        report = await client.get(
            BASE + f"/sample-imports/{sample_import['public_id']}/report", headers=headers
        )
        assert report.status_code == 200
        assert report.json()["rag_sandbox_eligible"] is True

        events = await client.get(
            BASE + f"/sample-imports/{sample_import['public_id']}/events", headers=headers
        )
        assert events.status_code == 200
        assert len(events.json()["items"]) > 0
    finally:
        await client.aclose()


async def test_file_endpoint_never_exposes_relative_path(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        sample_import = await _create_sample_import(
            client, headers, case["public_id"], case["candidate_public_id"]
        )
        settings = api_app.state.settings
        quarantine = ExternalDatasetQuarantineService(settings)
        quarantine.ensure_layout(sample_import["public_id"])
        quarantine.original_file_path(sample_import["public_id"], "note.txt").write_bytes(
            b"hello preview"
        )
        samples = DatasetSampleImportRepository(settings.resolved_database_path)
        file_record = samples.add_file(
            sample_import["public_id"],
            {
                "original_filename": "note.txt", "safe_filename": "note.txt",
                "relative_path": "note.txt", "status": "safe_for_scan",
            },
        )
        samples.update_file(file_record["public_id"], {"status": "safe_for_scan"})

        response = await client.get(
            BASE + f"/sample-imports/{sample_import['public_id']}/files/{file_record['public_id']}"
            "?preview=true",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "relative_path" not in body
        assert body["text_preview"] == "hello preview"
    finally:
        await client.aclose()


async def test_deletion_lifecycle_via_api(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        sample_import = await _create_sample_import(
            client, headers, case["public_id"], case["candidate_public_id"]
        )
        requested = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/request-deletion",
            headers=headers,
            json={"reason": "No longer needed"},
        )
        assert requested.status_code == 200, requested.text
        assert requested.json()["status"] == "requested"

        executed = await client.post(
            BASE + f"/sample-imports/{sample_import['public_id']}/execute-deletion",
            headers=headers,
        )
        assert executed.status_code == 200, executed.text
        assert executed.json()["status"] == "executed"

        refreshed = await client.get(
            BASE + f"/sample-imports/{sample_import['public_id']}", headers=headers
        )
        assert refreshed.json()["status"] == "deleted"
    finally:
        await client.aclose()


async def test_overview_returns_real_counts(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        await _create_sample_import(client, headers, case["public_id"], case["candidate_public_id"])
        response = await client.get(BASE + "/overview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "sample_imports_awaiting_approval" in body
        assert "quarantine_storage_used_bytes" in body
    finally:
        await client.aclose()


async def test_pagination_is_bounded(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        await _create_sample_import(client, headers, case["public_id"], case["candidate_public_id"])
        response = await client.get(
            BASE + "/sample-imports?page=1&page_size=200", headers=headers
        )
        assert response.status_code == 422  # page_size exceeds the le=100 bound
    finally:
        await client.aclose()


async def test_get_report_returns_404_before_finalize(api_app: FastAPI) -> None:
    case = _finalized_case(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        sample_import = await _create_sample_import(
            client, headers, case["public_id"], case["candidate_public_id"]
        )
        response = await client.get(
            BASE + f"/sample-imports/{sample_import['public_id']}/report", headers=headers
        )
        assert response.status_code == 404
    finally:
        await client.aclose()
