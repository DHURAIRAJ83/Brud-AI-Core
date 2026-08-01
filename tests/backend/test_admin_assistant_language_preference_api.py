import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
BASE = "/api/admin/assistant"


async def authenticated_client(app: FastAPI, *, username: str, password: str):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name=username, password=password)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def test_get_preference_requires_authentication(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{BASE}/preferences")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_new_admin_defaults_to_auto(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-default", password="Lang-Default-Pass-42"
    )
    try:
        response = await client.get(f"{BASE}/preferences", headers=headers)
        assert response.status_code == 200
        assert response.json()["response_language"] == "auto"
    finally:
        await client.aclose()


async def test_patch_preference_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-csrf", password="Lang-Csrf-Pass-42"
    )
    try:
        response = await client.patch(f"{BASE}/preferences", json={"response_language": "tamil"})
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_patch_and_get_preference_round_trip(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-roundtrip", password="Lang-Roundtrip-Pass-42"
    )
    try:
        patched = await client.patch(
            f"{BASE}/preferences", headers=headers, json={"response_language": "tanglish"}
        )
        assert patched.status_code == 200
        assert patched.json()["response_language"] == "tanglish"
        assert patched.json()["updated_at"]

        fetched = await client.get(f"{BASE}/preferences", headers=headers)
        assert fetched.json()["response_language"] == "tanglish"
    finally:
        await client.aclose()


async def test_patch_preference_rejects_invalid_enum(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-invalid", password="Lang-Invalid-Pass-42"
    )
    try:
        response = await client.patch(
            f"{BASE}/preferences", headers=headers, json={"response_language": "klingon"}
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_preferences_are_isolated_per_admin(api_app: FastAPI) -> None:
    client_a, headers_a = await authenticated_client(
        api_app, username="lang-admin-a", password="Lang-Admin-A-Pass-42"
    )
    client_b, headers_b = await authenticated_client(
        api_app, username="lang-admin-b", password="Lang-Admin-B-Pass-42"
    )
    try:
        await client_a.patch(
            f"{BASE}/preferences", headers=headers_a, json={"response_language": "tamil"}
        )
        await client_b.patch(
            f"{BASE}/preferences", headers=headers_b, json={"response_language": "english"}
        )
        result_a = await client_a.get(f"{BASE}/preferences", headers=headers_a)
        result_b = await client_b.get(f"{BASE}/preferences", headers=headers_b)
        assert result_a.json()["response_language"] == "tamil"
        assert result_b.json()["response_language"] == "english"
    finally:
        await client_a.aclose()
        await client_b.aclose()


async def test_preview_never_persists_a_preference(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-preview", password="Lang-Preview-Pass-42"
    )
    try:
        before = (await client.get(f"{BASE}/preferences", headers=headers)).json()
        preview = await client.post(
            f"{BASE}/preferences/preview",
            headers=headers,
            json={"message_text": "இது தமிழ்", "response_language_override": "tanglish"},
        )
        assert preview.status_code == 200
        assert preview.json()["resolved_language"] == "tanglish"

        after = (await client.get(f"{BASE}/preferences", headers=headers)).json()
        assert after["response_language"] == before["response_language"]
    finally:
        await client.aclose()


async def test_preview_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-preview-csrf", password="Lang-Preview-Csrf-Pass-42"
    )
    try:
        response = await client.post(
            f"{BASE}/preferences/preview", json={"message_text": "hello"}
        )
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_overview_includes_localized_guidance(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-overview", password="Lang-Overview-Pass-42"
    )
    try:
        await client.patch(
            f"{BASE}/preferences", headers=headers, json={"response_language": "tamil"}
        )
        response = await client.get(f"{BASE}/overview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["resolved_language"] == "tamil"
        assert isinstance(body["localized_guidance"], list)
        assert isinstance(body["guidance"], list)
    finally:
        await client.aclose()


async def test_chat_response_includes_resolved_language_fields(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-chat", password="Lang-Chat-Pass-42"
    )
    try:
        await client.patch(
            f"{BASE}/preferences", headers=headers, json={"response_language": "english"}
        )
        response = await client.post(
            f"{BASE}/chat",
            headers=headers,
            json={"message": "இது தமிழ் கேள்வி", "page_id": "overview"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["resolved_language"] == "english"
        assert body["language_source"] == "saved_admin_preference"
    finally:
        await client.aclose()


async def test_chat_request_override_does_not_persist(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(
        api_app, username="lang-chat-override", password="Lang-Chat-Override-Pass-42"
    )
    try:
        response = await client.post(
            f"{BASE}/chat",
            headers=headers,
            json={
                "message": "hello",
                "page_id": "overview",
                "response_language_override": "tanglish",
            },
        )
        assert response.status_code == 200
        assert response.json()["resolved_language"] == "tanglish"

        preference = await client.get(f"{BASE}/preferences", headers=headers)
        assert preference.json()["response_language"] == "auto"
    finally:
        await client.aclose()
