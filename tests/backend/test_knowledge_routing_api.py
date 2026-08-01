from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_endpoints_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/knowledge-routing/policy")
        assert response.status_code == 401
        response = await client.post(
            "/api/admin/knowledge-routing/classify", json={"text": "hello"}
        )
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_policy_endpoint_reports_valid_checksummed_policy(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/knowledge-routing/policy", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is True
        assert body["policy_checksum_sha256"]
    finally:
        await client.aclose()


async def test_reason_codes_endpoint_returns_full_registry(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get("/api/admin/knowledge-routing/reason-codes", headers=headers)
        assert response.status_code == 200
        assert response.json()["count"] > 50
    finally:
        await client.aclose()


async def test_classify_endpoint_returns_recommendation_only_and_persists(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-routing/classify",
            headers=headers,
            json={"text": "Python latest stable version?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["recommendation_only"] is True
        assert body["route_executed"] is False
        assert body["execution_route"] == "trusted_web"
        assert "public_id" in body

        listing = await client.get("/api/admin/knowledge-routing/decisions", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["count"] == 1

        detail = await client.get(
            f"/api/admin/knowledge-routing/decisions/{body['public_id']}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["domain"] == "computer_and_coding"
    finally:
        await client.aclose()


async def test_classify_endpoint_rejects_empty_text_with_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-routing/classify", headers=headers, json={"text": ""}
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_classify_endpoint_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        bad_headers = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
        response = await client.post(
            "/api/admin/knowledge-routing/classify", headers=bad_headers, json={"text": "hello"}
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_get_unknown_decision_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/knowledge-routing/decisions/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert response.status_code == 404
    finally:
        await client.aclose()


async def test_metrics_endpoint_reflects_classifications(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await client.post(
            "/api/admin/knowledge-routing/classify", headers=headers, json={"text": "hello there"}
        )
        response = await client.get("/api/admin/knowledge-routing/metrics", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_classifications"] == 1
    finally:
        await client.aclose()


async def test_classify_record_endpoint_works(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-routing/classify-record",
            headers=headers,
            json={
                "context_type": "rag_record",
                "record": {
                    "title": "Tamil Nadu government scheme update",
                    "tags": ["government_scheme"],
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["domain"] == "government_services"
    finally:
        await client.aclose()


async def test_chat_endpoint_is_unaffected_by_this_router(api_app: FastAPI) -> None:
    """Confirms the Phase 17 knowledge-routing router never touches the
    real Phase 18 public router -- unrelated concerns, same as before
    this test's name promised when the endpoint was still a placeholder."""

    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post("/api/chat", json={"message": "hello"})
        assert response.status_code == 200
        body = response.json()
        assert "route_used" in body
    finally:
        await client.aclose()
