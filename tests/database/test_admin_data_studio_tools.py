"""Phase 7: Admin Data Studio / Dataset Management -- Admin Assistant
integration.

Repository-wide audit (see the Phase 7 final report) found the entire
governed dataset lifecycle already built and extensively tested under
`docs/data_studio/` (source/rights registry, manual data studio, PDF/OCR
workspace, semantic chunk studio, quality/duplicate/conflict/approval
governance, dataset-version/RAG/training pipeline integration -- 1042+
backend tests, 82+ frontend tests, already passing). This phase adds
NO new dataset infrastructure -- only the three READ_ONLY Admin
Assistant tools this audit found were the sole genuine gap:

- `list_dataset_versions` / `get_dataset_version` -- wrap the existing
  `DatasetVersioningService` (pure `SELECT`, unmodified).
- `get_governance_duplicate_conflict_summary` -- wraps the existing
  `GovernanceDuplicateService`/`GovernanceConflictService.list_groups()`
  (pure `SELECT`, unmodified), summarized to counts-by-status rather
  than a raw member dump.

Duplicate/conflict *detection* logic itself is not re-tested here (see
tests/backend/test_governance_service.py's own 22 service tests) --
only that this tool wraps `list_groups()` correctly, is RBAC-gated, and
never mutates anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.services.admin_assistant_tool_governance import ToolAuthorizationError
from backend.services.admin_assistant_tools import READ_ONLY_TOOLS, ToolCapability, get_tool, run_tool
from tests.backend.test_dataset_api import authenticated_client, create_source, instruction

pytestmark = pytest.mark.anyio

NONE_ROLE_ADMIN_ID = "b0000000-0000-0000-0000-00000000000b"


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
        admin_role_overrides=f"{NONE_ROLE_ADMIN_ID}:NONE",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _approved_instruction(client, headers, source_id: str, text: str):
    created = (
        await client.post("/api/admin/datasets/records", headers=headers, json=instruction(source_id, text))
    ).json()
    await client.post(f"/api/admin/datasets/records/{created['public_id']}/submit", headers=headers)
    approved = await client.post(
        f"/api/admin/datasets/records/{created['public_id']}/review",
        headers=headers,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    return approved.json()


# --- 1: tool registration / capability metadata -----------------------------


def test_new_tools_are_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for name in (
        "list_dataset_versions", "get_dataset_version", "get_governance_duplicate_conflict_summary",
    ):
        tool = get_tool(name)
        assert tool is not None
        assert tool.capability is ToolCapability.READ_ONLY
        assert tool.needs_admin_id is False
        assert tool.pool_aware is False


# --- 2: RBAC still enforced through all three new tools ---------------------


@pytest.mark.parametrize(
    "name,params",
    [
        ("list_dataset_versions", {}),
        ("get_dataset_version", {"public_id": "whatever"}),
        ("get_governance_duplicate_conflict_summary", {}),
    ],
)
async def test_new_tools_denied_for_none_role(api_app: FastAPI, name: str, params: dict) -> None:
    settings = api_app.state.settings
    with pytest.raises(ToolAuthorizationError):
        run_tool(name, settings, params, admin_id=NONE_ROLE_ADMIN_ID)


# --- 3: empty-state shape (fresh DB, nothing built yet) ----------------------


async def test_list_dataset_versions_empty_state(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    result = run_tool("list_dataset_versions", settings, {}, admin_id="admin-x")
    assert result["available"] is True
    assert result["items"] == []


async def test_get_dataset_version_not_found(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    result = run_tool(
        "get_dataset_version", settings, {"public_id": "does-not-exist"}, admin_id="admin-x"
    )
    assert result["available"] is False
    assert result["reason"] == "dataset version not found"


async def test_governance_duplicate_conflict_summary_empty_state(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    result = run_tool("get_governance_duplicate_conflict_summary", settings, {}, admin_id="admin-x")
    assert result == {
        "available": True,
        "duplicate_group_count": 0,
        "duplicate_groups_by_status": {},
        "conflict_group_count": 0,
        "conflict_groups_by_status": {},
    }


# --- 4: real dataset version end to end (build -> validate -> run) ---------


async def test_list_and_get_dataset_version_reflect_a_real_build(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        for index in range(3):
            await _approved_instruction(client, headers, source["public_id"], f"தமிழ் பதில் {index}")

        build = await client.post(
            "/api/admin/datasets/builds",
            headers=headers,
            json={
                "dataset_name": "phase7_tool_test",
                "dataset_version": "v1",
                "minimum_quality_score": 0,
                "selection_filters": {"language": "ta"},
                "split_configuration": {
                    "train_percent": 90, "validation_percent": 5, "test_percent": 5, "seed": 42,
                },
            },
        )
        assert build.status_code == 200, build.text
        build_id = build.json()["public_id"]
        await client.post(f"/api/admin/datasets/builds/{build_id}/validate", headers=headers)
        run = await client.post(
            f"/api/admin/datasets/builds/{build_id}/run",
            headers=headers,
            json={"confirm": True, "allow_warnings": True},
        )
        assert run.status_code == 200, run.text
        version_public_id = run.json()["dataset_version_public_id"]

        settings = api_app.state.settings
        listed = run_tool("list_dataset_versions", settings, {}, admin_id="admin-x")
        assert listed["available"] is True
        version_ids = {item["public_id"] for item in listed["items"]}
        assert version_public_id in version_ids

        detail = run_tool(
            "get_dataset_version", settings, {"public_id": version_public_id}, admin_id="admin-x"
        )
        assert detail["available"] is True
        assert detail["public_id"] == version_public_id
        assert detail["status"] == "ready"
        assert detail["record_count"] == 3
    finally:
        await client.aclose()


# --- 5: tool call never mutates anything -------------------------------------


async def test_new_tools_are_read_only_in_practice(api_app: FastAPI) -> None:
    import sqlite3

    settings = api_app.state.settings
    db_path = settings.resolved_database_path

    def table_counts() -> dict[str, int]:
        conn = sqlite3.connect(db_path)
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        finally:
            conn.close()

    before = table_counts()
    run_tool("list_dataset_versions", settings, {}, admin_id="admin-x")
    run_tool("get_dataset_version", settings, {"public_id": "whatever"}, admin_id="admin-x")
    run_tool("get_governance_duplicate_conflict_summary", settings, {}, admin_id="admin-x")
    after = table_counts()

    assert before == after
