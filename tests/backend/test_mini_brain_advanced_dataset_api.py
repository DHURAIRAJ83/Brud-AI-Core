"""MB-05.1: API tests for /admin/mini-brain/dataset-advanced.

Auth/CSRF, all 11 routes, and the read-only security proof repeated
at the HTTP layer.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client, create_source, instruction

pytestmark = pytest.mark.anyio

MBDA = "/api/admin/mini-brain/dataset-advanced"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _seeded_source(client, headers, count: int = 20) -> str:
    source = await create_source(client, headers)
    for i in range(count):
        response = await client.post(
            "/api/admin/datasets/records", headers=headers,
            json=instruction(source["public_id"], output=f"பதில் {i}"),
        )
        assert response.status_code == 200
    return source["public_id"]


def _table_counts(db_path) -> dict[str, int]:
    with database_connection(db_path) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("dataset_sources", "dataset_records", "audit_logs")
        }


async def test_diagnostics_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get(f"{MBDA}/diagnostics")
        assert response.status_code == 401
    finally:
        await client.aclose()


async def test_conflicts_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBDA}/conflicts", json={"source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_all_ten_analysis_routes_work(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers)
        payload = {"source_public_id": source_id}
        for path in ("conflicts", "bias", "coverage", "difficulty", "curriculum", "knowledge-gap", "risk", "graph", "priority", "report"):
            response = await client.post(f"{MBDA}/{path}", headers=headers, json=payload)
            assert response.status_code == 200, f"{path} failed: {response.text}"
    finally:
        await client.aclose()


async def test_diagnostics_route(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBDA}/diagnostics", headers=headers)
        assert response.status_code == 200
        assert response.json()["ai_model_used"] is False
    finally:
        await client.aclose()


async def test_report_returns_explainable_scores(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers)
        response = await client.post(f"{MBDA}/report", headers=headers, json={"source_public_id": source_id})
        body = response.json()
        assert body["scores"]["overall"]["formula"]
        assert "reason" in body["scores"]["risk"]
    finally:
        await client.aclose()


async def test_all_routes_leave_dataset_tables_unchanged(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers)
        before = _table_counts(api_app.state.settings.resolved_database_path)

        payload = {"source_public_id": source_id}
        for path in ("conflicts", "bias", "coverage", "difficulty", "curriculum", "knowledge-gap", "risk", "graph", "priority", "report"):
            await client.post(f"{MBDA}/{path}", headers=headers, json=payload)
        await client.get(f"{MBDA}/diagnostics", headers=headers)

        after = _table_counts(api_app.state.settings.resolved_database_path)
        assert before == after
    finally:
        await client.aclose()


async def test_dataset_advanced_never_touches_runtime_state(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers, count=5)
        await client.post(f"{MBDA}/report", headers=headers, json={"source_public_id": source_id})
        status = await client.get("/api/admin/mini-brain/runtime/status", headers=headers)
        assert status.json()["state"] == "unloaded"
    finally:
        await client.aclose()
