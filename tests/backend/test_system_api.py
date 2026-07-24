import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.schema import SCHEMA_VERSION

pytestmark = pytest.mark.anyio


async def get(app: FastAPI, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/system/database",
        "/api/admin/system/configuration",
        "/api/admin/system/schema",
        "/api/admin/audit/recent",
    ],
)
async def test_system_endpoints_are_safe(protected_api_app: FastAPI, path: str) -> None:
    response = await get(protected_api_app, path)
    assert response.status_code == 200
    serialized = json.dumps(response.json())
    assert "/home/" not in serialized
    assert "/tmp/" not in serialized
    assert "BRUD_" not in serialized
    assert "do-not-expose" not in serialized


async def test_database_endpoint(protected_api_app: FastAPI) -> None:
    payload = (await get(protected_api_app, "/api/admin/system/database")).json()
    assert payload["status"] == "healthy"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["journal_mode"] == "wal"
    assert payload["foreign_keys"] is True
    assert payload["busy_timeout_ms"] == 5000


async def test_safe_configuration_endpoint(protected_api_app: FastAPI) -> None:
    payload = (await get(protected_api_app, "/api/admin/system/configuration")).json()
    assert set(payload) == {
        "environment",
        "debug",
        "log_level",
        "audit_enabled",
        "database_wal",
        "configured_origins",
    }


async def test_schema_and_audit_endpoints(protected_api_app: FastAPI) -> None:
    schema = (await get(protected_api_app, "/api/admin/system/schema")).json()
    assert schema["current_version"] == SCHEMA_VERSION
    assert schema["migration_status"] == "current"
    assert {item["name"] for item in schema["applied_migrations"]} == {
        "001_phase1_foundation",
        "002_phase2_foundation",
        "003_phase3_admin_dataset",
        "004_phase4_dataset_import",
        "005_phase5_document_processing",
        "006_phase6_dataset_versioning",
            "007_phase7_tokenizer_training",
            "008_phase8_core_model_architecture",
            "009_phase9_core_pretraining",
            "010_phase10_training_reliability",
            "011_phase11_base_pretraining_evaluation",
            "012_phase12_instruction_tuning",
            "013_phase13_multilingual_evaluation",
            "014_phase14_model_release_registry",
            "015_phase15_controlled_inference_runtime",
        }
    audit = (await get(protected_api_app, "/api/admin/audit/recent?limit=2")).json()
    assert audit["limit"] == 2
    assert audit["offset"] == 0
    assert audit["items"]
