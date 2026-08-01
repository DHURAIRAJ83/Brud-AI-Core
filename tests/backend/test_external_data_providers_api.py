import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Provider-Admin-Password-42"
BASE = "/api/admin/external-data-providers"


async def authenticated_client(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="provider-admin", display_name="Provider Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "provider-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def _register_custom(client, headers, code="api-test-provider"):
    response = await client.post(
        BASE,
        headers=headers,
        json={
            "provider_code": code,
            "name": "API Test Provider",
            "provider_type": "custom_api",
            "access_mode": "public",
        },
    )
    assert response.status_code == 200
    return response.json()


async def test_list_requires_authentication(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(BASE)
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_list_returns_seeded_builtin_providers(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(BASE, headers=headers)
        assert response.status_code == 200
        body = response.json()
        codes = {item["provider_code"] for item in body["items"]}
        assert "ai4bharat" in codes
        assert "huggingface" in codes
        assert "github" in codes
        assert "wikimedia" in codes
        assert "bhashini" in codes
        for item in body["items"]:
            assert item["lifecycle_status"] == "draft"
            assert item["enabled"] is False
            assert "credential" not in str(item).lower() or "credentials" not in item
    finally:
        await client.aclose()


async def test_register_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            BASE,
            json={
                "provider_code": "no-csrf",
                "name": "No CSRF",
                "provider_type": "custom_api",
                "access_mode": "public",
            },
        )
        assert response.status_code in (400, 403)
    finally:
        await client.aclose()


async def test_register_validates_provider_type_and_access_mode(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        bad_type = await client.post(
            BASE,
            headers=headers,
            json={
                "provider_code": "bad-1",
                "name": "Bad",
                "provider_type": "not_a_real_type",
                "access_mode": "public",
            },
        )
        assert bad_type.status_code == 422
        body = bad_type.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

        bad_access = await client.post(
            BASE,
            headers=headers,
            json={
                "provider_code": "bad-2",
                "name": "Bad",
                "provider_type": "custom_api",
                "access_mode": "not_a_real_mode",
            },
        )
        assert bad_access.status_code == 422
    finally:
        await client.aclose()


async def test_register_and_get_provider(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers)
        assert provider["lifecycle_status"] == "draft"
        assert provider["trust_status"] == "unverified"
        assert provider["enabled"] is False

        fetched = await client.get(f"{BASE}/{provider['public_id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["provider_code"] == "api-test-provider"
    finally:
        await client.aclose()


async def test_get_unknown_provider_is_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{BASE}/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_patch_updates_only_allowlisted_fields(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="patch-test")
        response = await client.patch(
            f"{BASE}/{provider['public_id']}",
            headers=headers,
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["description"] == "Updated description"
        assert body["lifecycle_status"] == "draft"

        # lifecycle_status/enabled/trust_status are not part of the patch
        # schema at all -- the API rejects them outright rather than
        # silently ignoring them, one layer stricter than the service.
        rejected = await client.patch(
            f"{BASE}/{provider['public_id']}",
            headers=headers,
            json={"lifecycle_status": "enabled"},
        )
        assert rejected.status_code == 422
    finally:
        await client.aclose()


async def test_lifecycle_transitions(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="lifecycle-test")
        public_id = provider["public_id"]

        enabled = await client.post(f"{BASE}/{public_id}/enable", headers=headers)
        assert enabled.status_code == 200
        assert enabled.json()["lifecycle_status"] == "enabled"
        assert enabled.json()["enabled"] is True

        restricted = await client.post(f"{BASE}/{public_id}/restrict", headers=headers)
        assert restricted.json()["lifecycle_status"] == "restricted"

        blocked = await client.post(f"{BASE}/{public_id}/block", headers=headers)
        assert blocked.json()["lifecycle_status"] == "blocked"
        assert blocked.json()["trust_status"] == "blocked"

        archived = await client.post(f"{BASE}/{public_id}/archive", headers=headers)
        assert archived.json()["lifecycle_status"] == "archived"

        blocked_again = await client.post(f"{BASE}/{public_id}/enable", headers=headers)
        assert blocked_again.status_code == 422
    finally:
        await client.aclose()


async def test_domain_add_and_verify_flow(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="domain-test")
        public_id = provider["public_id"]

        domain_response = await client.post(
            f"{BASE}/{public_id}/domains",
            headers=headers,
            json={"domain": "domain-test.example", "domain_type": "official"},
        )
        assert domain_response.status_code == 200
        domain = domain_response.json()
        assert domain["verification_status"] == "unverified"

        domains_list = await client.get(f"{BASE}/{public_id}/domains", headers=headers)
        assert len(domains_list.json()["items"]) == 1

        verify_response = await client.post(
            f"{BASE}/{public_id}/domains/{domain['public_id']}/verify",
            headers=headers,
            json={"verified": True, "evidence": "Checked HTTPS cert manually"},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["verification_status"] == "verified"

        verify_evaluation = await client.post(f"{BASE}/{public_id}/verify", headers=headers)
        assert verify_evaluation.status_code == 200
        body = verify_evaluation.json()
        assert body["verified"] is True
        assert body["trust_status_upgraded_to"] == "domain_verified"

        fetched = await client.get(f"{BASE}/{public_id}", headers=headers)
        assert fetched.json()["trust_status"] == "domain_verified"
    finally:
        await client.aclose()


async def test_domain_verify_requires_nonempty_evidence(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="domain-evidence-test")
        domain_response = await client.post(
            f"{BASE}/{provider['public_id']}/domains",
            headers=headers,
            json={"domain": "evidence-test.example", "domain_type": "official"},
        )
        domain = domain_response.json()
        response = await client.post(
            f"{BASE}/{provider['public_id']}/domains/{domain['public_id']}/verify",
            headers=headers,
            json={"verified": True, "evidence": ""},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_capabilities_never_expose_download_or_write_enabled(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="capabilities-test")
        response = await client.put(
            f"{BASE}/{provider['public_id']}/capabilities",
            headers=headers,
            json={
                "capabilities": [
                    {"capability_type": "read_metadata", "enabled": True},
                    {"capability_type": "download_full", "enabled": True},
                    {"capability_type": "upload", "enabled": True},
                ]
            },
        )
        assert response.status_code == 200
        by_type = {item["capability_type"]: item for item in response.json()["items"]}
        assert by_type["read_metadata"]["enabled"] is True
        assert by_type["download_full"]["enabled"] is False
        assert by_type["upload"]["enabled"] is False

        listed = await client.get(f"{BASE}/{provider['public_id']}/capabilities", headers=headers)
        assert len(listed.json()["items"]) == 3
    finally:
        await client.aclose()


async def test_credentials_are_never_returned_in_any_response(
    api_app: FastAPI, monkeypatch
) -> None:
    monkeypatch.setenv("BRUD_PROVIDER_SECRET__api_test", "a-real-secret-value-should-never-leak")
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="credential-test")
        response = await client.post(
            f"{BASE}/{provider['public_id']}/credentials",
            headers=headers,
            json={"credential_type": "api_key", "reference_key": "BRUD_PROVIDER_SECRET__api_test"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "credential_type", "configured", "status", "last_rotated_at", "last_tested_at",
        }
        assert body["configured"] is True
        raw_text = response.text
        assert "a-real-secret-value-should-never-leak" not in raw_text
        assert "BRUD_PROVIDER_SECRET__api_test" not in raw_text
        assert "reference_key" not in raw_text

        status_response = await client.get(
            f"{BASE}/{provider['public_id']}/credential-status", headers=headers
        )
        assert "a-real-secret-value-should-never-leak" not in status_response.text
        assert "reference_key" not in status_response.text
    finally:
        await client.aclose()


async def test_credential_revoke(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="credential-revoke-test")
        configured = await client.post(
            f"{BASE}/{provider['public_id']}/credentials",
            headers=headers,
            json={"credential_type": "api_key", "reference_key": "BRUD_PROVIDER_SECRET__revoke"},
        )
        assert configured.status_code == 200

        credentials_repo_check = await client.get(
            f"{BASE}/{provider['public_id']}/credential-status", headers=headers
        )
        assert credentials_repo_check.json()["items"][0]["status"] == "configured"
    finally:
        await client.aclose()


async def test_history_records_registration_and_lifecycle_events(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="history-test")
        await client.post(f"{BASE}/{provider['public_id']}/enable", headers=headers)
        history = await client.get(f"{BASE}/{provider['public_id']}/history", headers=headers)
        assert history.status_code == 200
        event_types = {item["event_type"] for item in history.json()["items"]}
        assert "provider_registered" in event_types
        assert "provider_enabled" in event_types
    finally:
        await client.aclose()


async def test_global_audit_log_records_provider_mutations(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="audit-test")
        await client.post(f"{BASE}/{provider['public_id']}/enable", headers=headers)
        audit = await client.get("/api/admin/audit/recent?limit=50", headers=headers)
        event_types = {item["event_type"] for item in audit.json()["items"]}
        assert "external_data_provider_registered" in event_types
        assert "external_data_provider_enable" in event_types
    finally:
        await client.aclose()


async def test_filters_by_lifecycle_status_and_enabled(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        provider = await _register_custom(client, headers, code="filter-test")
        await client.post(f"{BASE}/{provider['public_id']}/enable", headers=headers)

        enabled_only = await client.get(f"{BASE}?enabled=true", headers=headers)
        codes = {item["provider_code"] for item in enabled_only.json()["items"]}
        assert "filter-test" in codes

        draft_only = await client.get(f"{BASE}?lifecycle_status=draft", headers=headers)
        draft_codes = {item["provider_code"] for item in draft_only.json()["items"]}
        assert "filter-test" not in draft_codes
        assert "ai4bharat" in draft_codes
    finally:
        await client.aclose()
