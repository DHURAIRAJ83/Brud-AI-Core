"""MB-02: Brud Knowledge Core -- API tests.

Covers seeding, structured search (never semantic), relationships,
validation, and coverage. No model, no embeddings, no vector search
anywhere in this module -- these tests exist partly to prove that too.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBKC = "/api/admin/mini-brain/knowledge-core"


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


async def _seed(client, headers):
    response = await client.post(f"{MBKC}/seed", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_domains_are_empty_before_seeding(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBKC}/domains", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []
    finally:
        await client.aclose()


async def test_seed_is_real_and_idempotent(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        first = await _seed(client, headers)
        assert first["seeded"] is True
        assert first["domains"] == 7
        assert first["items"] > 0
        assert first["relationships"] > 0

        second = await _seed(client, headers)
        assert second["seeded"] is False
        assert second["reason"] == "already_seeded"

        domains = await client.get(f"{MBKC}/domains", headers=headers)
        assert len(domains.json()["items"]) == 7
        assert sum(d["item_count"] for d in domains.json()["items"]) == first["items"]
    finally:
        await client.aclose()


async def test_seed_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBKC}/seed")
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_structured_search_finds_seeded_item(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.get(f"{MBKC}/search", headers=headers, params={"q": "tokenizer"})
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()["items"]]
        assert "Tokenizer Training" in titles
    finally:
        await client.aclose()


async def test_search_by_domain_and_category_filters(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.get(
            f"{MBKC}/search", headers=headers,
            params={"domain": "rag", "category": "Module"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0
        assert all(item["category"] == "Module" for item in items)
    finally:
        await client.aclose()


async def test_item_detail_includes_resolved_relationships(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        search = await client.get(f"{MBKC}/search", headers=headers, params={"q": "Dataset Export"})
        item_id = search.json()["items"][0]["public_id"]

        detail = await client.get(f"{MBKC}/items/{item_id}", headers=headers)
        assert detail.status_code == 200
        relationships = detail.json()["relationships"]
        assert any(r["related_item_title"] == "Tokenizer Training" for r in relationships)
    finally:
        await client.aclose()


async def test_create_item_rejects_duplicate_title_in_same_domain(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        payload = {
            "domain": "architecture", "title": "core_model / backend split",
            "category": "Pattern", "description": "duplicate attempt",
        }
        response = await client.post(f"{MBKC}/items", headers=headers, json=payload)
        assert response.status_code == 422, response.text
    finally:
        await client.aclose()


async def test_create_item_in_unknown_domain_is_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        payload = {"domain": "not_a_real_domain", "title": "X", "category": "Y"}
        response = await client.post(f"{MBKC}/items", headers=headers, json=payload)
        assert response.status_code == 422, response.text
    finally:
        await client.aclose()


async def test_validation_finds_real_issues_in_seed_data(api_app: FastAPI) -> None:
    """The seed data is honest, not perfect -- some items really do
    lack related_documentation. This proves the validator actually
    inspects content rather than always reporting zero issues."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.post(f"{MBKC}/validate", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["issue_count"] > 0
        assert "missing_documentation" in body["summary"]
        # The seed data was built with no duplicate titles, valid
        # versions, and every item assigned a category -- these
        # issue types must be genuinely absent, not just unchecked.
        assert "duplicate_item" not in body["summary"]
        assert "missing_category" not in body["summary"]
        assert "invalid_version" not in body["summary"]
        assert "broken_reference" not in body["summary"]
    finally:
        await client.aclose()


async def test_validation_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBKC}/validate")
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_validation_report_is_persisted_and_listed(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        await client.post(f"{MBKC}/validate", headers=headers)
        reports = await client.get(f"{MBKC}/validation-reports", headers=headers)
        assert reports.status_code == 200
        assert len(reports.json()["items"]) == 1
    finally:
        await client.aclose()


async def test_coverage_reports_honest_non_100_percent_numbers(api_app: FastAPI) -> None:
    """Coverage must never claim complete coverage for a seed that is
    explicitly a representative sample, not an exhaustive catalog."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.get(f"{MBKC}/coverage", headers=headers)
        assert response.status_code == 200
        overall = response.json()["overall"]
        assert overall["total_items"] > 0
        assert overall["catalog_coverage_pct"] is not None
        assert overall["catalog_coverage_pct"] < 100
    finally:
        await client.aclose()


async def test_diagnostics_reports_seeded_state(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.get(f"{MBKC}/diagnostics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["seeded"] is True
        assert body["domain_count"] == 7
        assert body["relationship_count"] > 0
    finally:
        await client.aclose()


async def test_knowledge_core_never_touches_admin_assistant_or_inference_runtime(
    api_app: FastAPI,
) -> None:
    """Direct proof of independence, same discipline as MB-01's own test."""

    from backend.database.connection import database_connection

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        await client.post(f"{MBKC}/validate", headers=headers)
        await client.get(f"{MBKC}/coverage", headers=headers)
    finally:
        await client.aclose()

    with database_connection(api_app.state.settings.resolved_database_path) as connection:
        approvals = connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0]
        assignments = connection.execute(
            "SELECT COUNT(*) FROM inference_model_assignments"
        ).fetchone()[0]
        assert approvals == 0
        assert assignments == 0
