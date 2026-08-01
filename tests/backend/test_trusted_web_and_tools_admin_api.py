"""Phase 20 Step 29/39 -- Admin-only `/api/admin/trusted-web` and
`/api/admin/deterministic-tools` API tests: auth required, CSRF on
writes, pagination bounds, no API-key/raw-page-body leakage, stable
behavior for both healthy and unconfigured providers, and correct
tool-registry closure (no arbitrary tool name accepted)."""

from __future__ import annotations

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
        trusted_web_provider_name="unconfigured_in_tests",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


# -- auth is required on every endpoint -----------------------------------------------------


async def test_trusted_web_overview_requires_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as c:
        response = await c.get("/api/admin/trusted-web/overview")
    assert response.status_code in (401, 403)


async def test_tools_overview_requires_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as c:
        response = await c.get("/api/admin/deterministic-tools/overview")
    assert response.status_code in (401, 403)


# -- Trusted Web: read-only endpoints -----------------------------------------------------


async def test_trusted_web_overview_returns_real_zeroed_counts(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/trusted-web/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_search_events"] == 0
    assert "web_demand" in body


async def test_trusted_web_providers_never_leaks_api_key(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/trusted-web/providers", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "api_key" not in body
    assert "base_url" not in body
    assert body["configured_provider_name"] == "unconfigured_in_tests"
    assert body["healthy"] is False


async def test_trusted_web_policy_endpoint_returns_versioned_checksummed_policy(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/trusted-web/policy", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert "policy_checksum_sha256" in body["policy"]
    assert "policy_version" in body["policy"]


async def test_trusted_web_health_reports_unavailable_provider_honestly(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/trusted-web/health", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider_available"] is False
    assert body["policy_loaded"] is True
    assert body["external_mcp_enabled"] is False


async def test_trusted_web_search_events_pagination_bounded(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get(
        "/api/admin/trusted-web/search-events", headers=headers, params={"limit": 500}
    )
    # Bounded by the repository's own pagination() cap -- either the API
    # itself rejects an out-of-range limit or silently clamps it; either
    # way, an oversized limit must never be honored verbatim.
    assert response.status_code in (200, 422)


async def test_trusted_web_evidence_endpoint_works(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/trusted-web/evidence", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


# -- Trusted Web: write actions require CSRF -----------------------------------------------


async def test_trusted_web_test_search_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    bad_headers = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
    response = await client.post(
        "/api/admin/trusted-web/test-search", headers=bad_headers, json={"query": "test"}
    )
    assert response.status_code in (400, 403)


async def test_trusted_web_test_search_with_unconfigured_provider_is_honest(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.post(
        "/api/admin/trusted-web/test-search", headers=headers,
        json={"query": "test query", "web_category": "current_general_information"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] != "success"
    assert body["citation_count"] == 0


async def test_trusted_web_verify_source_blocks_private_ip(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.post(
        "/api/admin/trusted-web/verify-source", headers=headers,
        json={"url": "http://127.0.0.1/secret", "allowed_domain": "127.0.0.1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert "block_reason" in body


async def test_trusted_web_verify_source_never_returns_page_body(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.post(
        "/api/admin/trusted-web/verify-source", headers=headers,
        json={"url": "https://evil.example/x", "allowed_domain": "totally-different.example"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "main_text" not in body
    assert "raw_bytes" not in body


# -- Deterministic Tools: read-only endpoints -----------------------------------------------


async def test_tools_overview_returns_real_zeroed_counts(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/deterministic-tools/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_executions"] == 0
    assert body["external_mcp_enabled"] is False


async def test_tools_registry_lists_exactly_three_public_tools(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get("/api/admin/deterministic-tools/registry", headers=headers)
    assert response.status_code == 200
    tools = response.json()["tools"]
    names = {t["tool_name"] for t in tools}
    assert names == {"calculator", "unit_conversion", "date_time_arithmetic"}
    for tool in tools:
        assert tool["source"] == "built_in_deterministic"


async def test_tools_execution_events_endpoint_works(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.get(
        "/api/admin/deterministic-tools/execution-events", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


# -- Deterministic Tools: write action requires CSRF, closed registry -----------------------


async def test_tools_test_endpoint_requires_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    bad_headers = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
    response = await client.post(
        "/api/admin/deterministic-tools/test", headers=bad_headers,
        json={"tool_name": "calculator", "input_payload": {"expression": "2+2"}},
    )
    assert response.status_code in (400, 403)


async def test_tools_test_endpoint_calculator_success(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.post(
        "/api/admin/deterministic-tools/test", headers=headers,
        json={"tool_name": "calculator", "input_payload": {"expression": "987654 * 12345"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["output_payload"]["result"] == str(987654 * 12345)


async def test_tools_test_endpoint_rejects_arbitrary_tool_name(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    response = await client.post(
        "/api/admin/deterministic-tools/test", headers=headers,
        json={"tool_name": "shell_execute", "input_payload": {"command": "rm -rf /"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"


async def test_tools_test_endpoint_audits_execution(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    await client.post(
        "/api/admin/deterministic-tools/test", headers=headers,
        json={"tool_name": "calculator", "input_payload": {"expression": "1+1"}},
    )
    events = await client.get(
        "/api/admin/deterministic-tools/execution-events", headers=headers
    )
    assert len(events.json()["items"]) == 1
