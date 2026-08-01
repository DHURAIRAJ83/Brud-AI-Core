import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Discovery-Admin-Password-42"
BASE = "/api/admin/dataset-discovery"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="discovery-admin", display_name="Discovery Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "discovery-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def _create_session(client, headers, title="Tamil ASR search"):
    response = await client.post(BASE + "/sessions", headers=headers, json={"title": title})
    assert response.status_code == 200
    return response.json()


async def test_list_sessions_requires_authentication(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(BASE + "/sessions")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_create_session_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(BASE + "/sessions", json={"title": "No CSRF"})
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_create_and_get_session(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        assert session["status"] == "draft"

        fetched = await client.get(BASE + f"/sessions/{session['public_id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["public_id"] == session["public_id"]

        listed = await client.get(BASE + "/sessions", headers=headers)
        assert listed.status_code == 200
        assert session["public_id"] in {item["public_id"] for item in listed.json()["items"]}
    finally:
        await client.aclose()


async def test_set_and_get_requirements(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        response = await client.put(
            BASE + f"/sessions/{session['public_id']}/requirements",
            headers=headers,
            json={"modality": "text", "languages": ["tamil"], "tasks": ["asr"]},
        )
        assert response.status_code == 200
        assert response.json()["languages"] == ["tamil"]

        fetched = await client.get(
            BASE + f"/sessions/{session['public_id']}/requirements", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["tasks"] == ["asr"]

        session_after = await client.get(
            BASE + f"/sessions/{session['public_id']}", headers=headers
        )
        assert session_after.json()["status"] == "ready"
    finally:
        await client.aclose()


async def test_run_search_with_no_enabled_providers_returns_failed_status(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        await client.put(
            BASE + f"/sessions/{session['public_id']}/requirements",
            headers=headers,
            json={"languages": ["tamil"]},
        )
        response = await client.post(
            BASE + f"/sessions/{session['public_id']}/search", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["provider_count"] == 0
    finally:
        await client.aclose()


async def test_run_search_without_requirements_is_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        response = await client.post(
            BASE + f"/sessions/{session['public_id']}/search", headers=headers
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_cancel_session(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        response = await client.post(
            BASE + f"/sessions/{session['public_id']}/cancel", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

        again = await client.post(
            BASE + f"/sessions/{session['public_id']}/cancel", headers=headers
        )
        assert again.status_code == 422
    finally:
        await client.aclose()


async def test_manual_candidate_lifecycle(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        created = await client.post(
            BASE + f"/sessions/{session['public_id']}/candidates",
            headers=headers,
            json={
                "canonical_name": "Manually Found Tamil Corpus",
                "declared_licence": "cc-by-4.0",
                "languages": ["tamil"],
            },
        )
        assert created.status_code == 200
        candidate = created.json()
        assert candidate["candidate_entry_method"] == "manual"
        assert candidate["normalized_name"] == "manually found tamil corpus"

        listed = await client.get(
            BASE + f"/sessions/{session['public_id']}/candidates", headers=headers
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        detail = await client.get(BASE + f"/candidates/{candidate['public_id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["sources"] == []
        assert detail.json()["scores"] == []

        excluded = await client.post(
            BASE + f"/candidates/{candidate['public_id']}/exclude", headers=headers
        )
        assert excluded.status_code == 200
        assert excluded.json()["excluded"] is True

        visible_only = await client.get(
            BASE + f"/sessions/{session['public_id']}/candidates?include_excluded=false",
            headers=headers,
        )
        assert visible_only.json()["items"] == []

        restored = await client.post(
            BASE + f"/candidates/{candidate['public_id']}/restore", headers=headers
        )
        assert restored.status_code == 200
        assert restored.json()["excluded"] is False
    finally:
        await client.aclose()


async def test_manual_candidate_requires_canonical_name(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        response = await client.post(
            BASE + f"/sessions/{session['public_id']}/candidates", headers=headers, json={}
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_comparison_requires_two_to_five_candidates(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        created = await client.post(
            BASE + f"/sessions/{session['public_id']}/candidates",
            headers=headers,
            json={"canonical_name": "Solo Candidate"},
        )
        candidate_id = created.json()["public_id"]

        too_few = await client.post(
            BASE + f"/sessions/{session['public_id']}/comparisons",
            headers=headers,
            json={"candidate_ids": [candidate_id]},
        )
        assert too_few.status_code in (400, 422)
    finally:
        await client.aclose()


async def test_create_and_fetch_comparison(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        first = (
            await client.post(
                BASE + f"/sessions/{session['public_id']}/candidates",
                headers=headers,
                json={"canonical_name": "First Candidate"},
            )
        ).json()
        second = (
            await client.post(
                BASE + f"/sessions/{session['public_id']}/candidates",
                headers=headers,
                json={"canonical_name": "Second Candidate"},
            )
        ).json()

        response = await client.post(
            BASE + f"/sessions/{session['public_id']}/comparisons",
            headers=headers,
            json={"candidate_ids": [first["public_id"], second["public_id"]]},
        )
        assert response.status_code == 200
        comparison = response.json()
        assert set(comparison["candidate_ids"]) == {first["public_id"], second["public_id"]}

        listed = await client.get(
            BASE + f"/sessions/{session['public_id']}/comparisons", headers=headers
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        fetched = await client.get(
            BASE + f"/comparisons/{comparison['public_id']}", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["public_id"] == comparison["public_id"]
    finally:
        await client.aclose()


async def test_events_and_provider_runs_endpoints(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        session = await _create_session(client, headers)
        events = await client.get(
            BASE + f"/sessions/{session['public_id']}/events", headers=headers
        )
        assert events.status_code == 200
        assert any(item["event_type"] == "session_created" for item in events.json()["items"])

        runs = await client.get(
            BASE + f"/sessions/{session['public_id']}/provider-runs", headers=headers
        )
        assert runs.status_code == 200
        assert runs.json()["items"] == []
    finally:
        await client.aclose()
