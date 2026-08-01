import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Verification-Admin-Password-42"
BASE = "/api/admin/dataset-verification"
ADMIN_USERNAME = "verification-admin"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=ADMIN_USERNAME, display_name="Verification Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


def _create_candidate(app: FastAPI, *, declared_licence: str | None = "CC-BY-4.0") -> str:
    discovery = ExternalDatasetDiscoveryRepository(app.state.settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": "system"}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {
            "canonical_name": "Tamil Corpus",
            "normalized_name": "tamil corpus",
            "declared_licence": declared_licence,
        },
    )
    return candidate["public_id"]


async def _create_case(client, headers, candidate_public_id: str) -> dict:
    response = await client.post(
        BASE + "/cases", headers=headers, json={"candidate_public_id": candidate_public_id}
    )
    assert response.status_code == 200
    return response.json()


async def test_list_cases_requires_authentication(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(BASE + "/cases")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_create_case_requires_csrf(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            BASE + "/cases", json={"candidate_public_id": candidate_public_id}
        )
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_create_get_list_case(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        assert case["status"] == "draft"
        assert case["candidate_public_id"] == candidate_public_id

        fetched = await client.get(BASE + f"/cases/{case['public_id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["public_id"] == case["public_id"]

        listed = await client.get(BASE + "/cases", headers=headers)
        assert listed.status_code == 200
        assert case["public_id"] in {item["public_id"] for item in listed.json()["items"]}
    finally:
        await client.aclose()


async def test_duplicate_active_case_rejected(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        await _create_case(client, headers, candidate_public_id)
        response = await client.post(
            BASE + "/cases", headers=headers, json={"candidate_public_id": candidate_public_id}
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_start_and_cancel_case(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        started = await client.post(BASE + f"/cases/{case['public_id']}/start", headers=headers)
        assert started.status_code == 200
        assert started.json()["status"] == "collecting_evidence"

        cancelled = await client.post(BASE + f"/cases/{case['public_id']}/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
    finally:
        await client.aclose()


async def test_manual_evidence_and_list(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        response = await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        )
        assert response.status_code == 200
        assert response.json()["retrieval_status"] == "manual"

        listed = await client.get(BASE + f"/cases/{case['public_id']}/evidence", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_licence_assess_and_permission_assess_and_review_flow(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        )
        licence_response = await client.post(
            BASE + f"/cases/{case['public_id']}/licence/assess", headers=headers
        )
        assert licence_response.status_code == 200
        assert licence_response.json()["licence_status"] == "verified"

        assess_response = await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/assess", headers=headers
        )
        assert assess_response.status_code == 200
        assert "rag_use" in assess_response.json()["items"]

        commercial_response = await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/commercial-use",
            headers=headers,
            json={"intended_use_category": "research"},
        )
        assert commercial_response.status_code == 200
        assert commercial_response.json()["status"] != "likely_allowed"

        review_response = await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/rag_use/review",
            headers=headers,
            json={"status": "approved", "reason": "Licence file confirms CC-BY-4.0"},
        )
        assert review_response.status_code == 200
        assert review_response.json()["status"] == "approved"

        listed = await client.get(BASE + f"/cases/{case['public_id']}/permissions", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) > 0
    finally:
        await client.aclose()


async def test_review_permission_without_reason_rejected(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/assess", headers=headers
        )
        response = await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/rag_use/review",
            headers=headers,
            json={"status": "approved", "reason": ""},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_upstream_source_add_and_verify(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        added = await client.post(
            BASE + f"/cases/{case['public_id']}/upstreams",
            headers=headers,
            json={"upstream_name": "Common Voice"},
        )
        assert added.status_code == 200
        upstream_public_id = added.json()["public_id"]

        verified = await client.post(
            BASE + f"/cases/{case['public_id']}/upstreams/{upstream_public_id}/verify",
            headers=headers,
            json={"verification_status": "verified"},
        )
        assert verified.status_code == 200
        assert verified.json()["verification_status"] == "verified"

        listed = await client.get(BASE + f"/cases/{case['public_id']}/upstreams", headers=headers)
        assert len(listed.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_conflict_detect_and_resolve(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-NC-4.0."},
        )
        await client.post(BASE + f"/cases/{case['public_id']}/licence/assess", headers=headers)

        detected = await client.post(
            BASE + f"/cases/{case['public_id']}/conflicts/detect", headers=headers
        )
        assert detected.status_code == 200
        conflicts = detected.json()["items"]
        assert len(conflicts) == 1

        resolved = await client.post(
            BASE + f"/cases/{case['public_id']}/conflicts/{conflicts[0]['public_id']}/resolve",
            headers=headers,
            json={"resolution_status": "resolved", "resolution_reason": "Confirmed licence"},
        )
        assert resolved.status_code == 200

        listed = await client.get(BASE + f"/cases/{case['public_id']}/conflicts", headers=headers)
        assert listed.status_code == 200
    finally:
        await client.aclose()


async def test_finalize_report_and_events(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        )
        await client.post(BASE + f"/cases/{case['public_id']}/licence/assess", headers=headers)
        await client.post(BASE + f"/cases/{case['public_id']}/permissions/assess", headers=headers)

        finalized = await client.post(
            BASE + f"/cases/{case['public_id']}/finalize", headers=headers
        )
        assert finalized.status_code == 200
        assert finalized.json()["locked_at"] is not None

        report = await client.get(BASE + f"/cases/{case['public_id']}/report", headers=headers)
        assert report.status_code == 200
        assert report.json()["report"]["licence_status"]["value"] == "verified"

        events = await client.get(BASE + f"/cases/{case['public_id']}/events", headers=headers)
        assert events.status_code == 200
        assert any(e["event_type"] == "case_finalized" for e in events.json()["items"])
    finally:
        await client.aclose()


async def test_withdrawal_notice_create_and_list(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        created = await client.post(
            BASE + f"/cases/{case['public_id']}/withdrawal-notices",
            headers=headers,
            json={"notice_type": "licence_changed", "notice_text": "Rights holder changed terms"},
        )
        assert created.status_code == 200
        assert created.json()["impact_status"] == "assessed"

        listed = await client.get(
            BASE + f"/cases/{case['public_id']}/withdrawal-notices", headers=headers
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        case_after = await client.get(BASE + f"/cases/{case['public_id']}", headers=headers)
        assert case_after.json()["verification_expiry_status"] == "withdrawn"
    finally:
        await client.aclose()


async def test_withdrawal_notice_rejects_unknown_type(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        response = await client.post(
            BASE + f"/cases/{case['public_id']}/withdrawal-notices",
            headers=headers,
            json={"notice_type": "not_a_real_type"},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_overview_counts_reflect_real_case_state(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)

        before = await client.get(BASE + "/overview", headers=headers)
        assert before.status_code == 200
        assert before.json()["candidates_awaiting_verification"] >= 1

        await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        )
        await client.post(BASE + f"/cases/{case['public_id']}/licence/assess", headers=headers)

        after = await client.get(BASE + "/overview", headers=headers)
        assert after.status_code == 200
        body = after.json()
        assert set(body) == {
            "candidates_awaiting_verification", "verification_cases_in_review",
            "missing_licence_cases", "conflicting_evidence_cases",
            "training_permission_approved", "commercial_permission_approved",
            "verification_expired",
        }
    finally:
        await client.aclose()


async def test_permission_reviews_list_reflects_review_history(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/assess", headers=headers
        )
        await client.post(
            BASE + f"/cases/{case['public_id']}/permissions/rag_use/review",
            headers=headers,
            json={"status": "approved", "reason": "Licence file confirms CC-BY-4.0"},
        )
        reviews = await client.get(
            BASE + f"/cases/{case['public_id']}/permissions/reviews", headers=headers
        )
        assert reviews.status_code == 200
        items = reviews.json()["items"]
        assert len(items) == 1
        assert items[0]["decision"] == "approved"
        assert items[0]["permission_type"] == "rag_use"
    finally:
        await client.aclose()


async def test_source_rights_existing_source_absent_by_default(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        response = await client.get(
            BASE + f"/cases/{case['public_id']}/source-rights/existing-source", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["existing_source"] is None
    finally:
        await client.aclose()


async def test_source_rights_draft_proposal_requires_finalized_case(api_app: FastAPI) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        response = await client.post(
            BASE + f"/cases/{case['public_id']}/source-rights/draft-proposal", headers=headers
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_source_rights_draft_proposal_after_finalize_without_existing_source(
    api_app: FastAPI,
) -> None:
    candidate_public_id = _create_candidate(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        case = await _create_case(client, headers, candidate_public_id)
        await client.post(
            BASE + f"/cases/{case['public_id']}/evidence/manual",
            headers=headers,
            json={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        )
        await client.post(BASE + f"/cases/{case['public_id']}/licence/assess", headers=headers)
        await client.post(BASE + f"/cases/{case['public_id']}/permissions/assess", headers=headers)
        await client.post(BASE + f"/cases/{case['public_id']}/finalize", headers=headers)

        response = await client.post(
            BASE + f"/cases/{case['public_id']}/source-rights/draft-proposal", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["drafted"] is False
        assert "reason" in body
    finally:
        await client.aclose()
