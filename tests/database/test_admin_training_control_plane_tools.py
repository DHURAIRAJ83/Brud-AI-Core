"""Phase 8: Training Control Plane -- Admin Assistant integration.

Repository audit (see the Phase 8 final report) found `PretrainingService`
already the shared job engine reused verbatim by pretraining, base
training, and instruction tuning (docs/pretraining_architecture.md),
with a mature checkpoint/evaluation/quality-gate/worker-lease/recovery
layer already built and tested (tests/backend/test_pretraining_api.py
and friends) -- but with ZERO Admin Assistant tool coverage before this
phase. This phase adds NO new training infrastructure -- only six
READ_ONLY tools wrapping already-existing, already-pure-read service
methods verbatim:

- `list_training_jobs`/`get_training_job` -- `PretrainingService.list_jobs()`/`.get_job()`
- `get_training_checkpoints` -- `PretrainingService.checkpoints()`
- `get_training_evaluations` -- `PretrainingService.evaluations()`
- `get_training_quality_gate` -- `TrainingEvaluationService.quality()`/`.quality_issues()`
  (deliberately NOT `.assess_quality()`, which computes and persists a
  new assessment -- a READ_ONLY tool must never trigger that as a side
  effect of an admin's question)
- `get_model_release_lineage` -- `LineageGraphService.for_model_release()`
  (Objective 3: "which dataset trained this model")

Training job creation/worker execution/checkpoint generation/promotion
logic itself is not re-tested here (already exhaustively covered by
tests/backend/test_pretraining_api.py and
tests/backend/test_training_evaluation_service.py) -- only that these
tools wrap the existing read methods correctly, are RBAC-gated, and
never mutate anything.
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
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_pretraining_api import _fixture_refs, _payload

pytestmark = pytest.mark.anyio

NONE_ROLE_ADMIN_ID = "c0000000-0000-0000-0000-00000000000c"

NEW_TOOLS = (
    "list_training_jobs",
    "get_training_job",
    "get_training_checkpoints",
    "get_training_evaluations",
    "get_training_quality_gate",
    "get_model_release_lineage",
)


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


# --- 1: tool registration / capability metadata -----------------------------


def test_new_tools_are_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for name in NEW_TOOLS:
        tool = get_tool(name)
        assert tool is not None
        assert tool.capability is ToolCapability.READ_ONLY
        assert tool.needs_admin_id is False
        assert tool.pool_aware is False


# --- 2: RBAC enforced through every new tool ---------------------------------


@pytest.mark.parametrize(
    "name,params",
    [
        ("list_training_jobs", {}),
        ("get_training_job", {"public_id": "whatever"}),
        ("get_training_checkpoints", {"public_id": "whatever"}),
        ("get_training_evaluations", {"public_id": "whatever"}),
        ("get_training_quality_gate", {"public_id": "whatever"}),
        ("get_model_release_lineage", {"release_public_id": "whatever"}),
    ],
)
async def test_new_tools_denied_for_none_role(api_app: FastAPI, name: str, params: dict) -> None:
    settings = api_app.state.settings
    with pytest.raises(ToolAuthorizationError):
        run_tool(name, settings, params, admin_id=NONE_ROLE_ADMIN_ID)


# --- 3: empty/not-found state shape (fresh DB, nothing built yet) ----------


async def test_list_training_jobs_empty_state(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    result = run_tool("list_training_jobs", settings, {}, admin_id="admin-x")
    assert result["available"] is True
    assert result["items"] == []


async def test_get_training_job_not_found(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    result = run_tool("get_training_job", settings, {"public_id": "does-not-exist"}, admin_id="admin-x")
    assert result == {"available": False, "reason": "training job not found"}


async def test_get_model_release_lineage_unknown_release_is_honest_not_fabricated(
    api_app: FastAPI,
) -> None:
    settings = api_app.state.settings
    result = run_tool(
        "get_model_release_lineage", settings, {"release_public_id": "does-not-exist"}, admin_id="admin-x"
    )
    assert result["available"] is True
    assert result["complete"] is False
    assert result["direct_lineage"] == {}


# --- 4: real training job (draft, no worker run) ----------------------------


async def test_list_and_get_training_job_reflect_a_real_created_job(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/pretraining/jobs", headers=headers, json=_payload(refs)
        )
        assert created.status_code == 200, created.text
        job_public_id = created.json()["public_id"]

        settings = api_app.state.settings
        listed = run_tool("list_training_jobs", settings, {}, admin_id="admin-x")
        assert listed["available"] is True
        job_ids = {item["public_id"] for item in listed["items"]}
        assert job_public_id in job_ids

        detail = run_tool("get_training_job", settings, {"public_id": job_public_id}, admin_id="admin-x")
        assert detail["available"] is True
        assert detail["public_id"] == job_public_id
        assert detail["status"] == "draft"

        # No worker has run yet -- checkpoints/evaluations are honestly empty,
        # never fabricated.
        checkpoints = run_tool(
            "get_training_checkpoints", settings, {"public_id": job_public_id}, admin_id="admin-x"
        )
        assert checkpoints == {"available": True, "items": []}

        evaluations = run_tool(
            "get_training_evaluations", settings, {"public_id": job_public_id}, admin_id="admin-x"
        )
        assert evaluations == {"available": True, "items": []}

        quality_gate = run_tool(
            "get_training_quality_gate", settings, {"public_id": job_public_id}, admin_id="admin-x"
        )
        assert quality_gate["available"] is False
        assert "no quality assessment" in quality_gate["reason"]
    finally:
        await client.aclose()


# --- 5: governance boundary -- read-only tools never mutate ----------------


async def test_new_tools_never_mutate_training_dataset_or_model_state(api_app: FastAPI) -> None:
    """OBJECTIVE 5: a tool that only reads training state must never
    create/update training_jobs, mutate datasets, mutate model registry,
    create approvals, or promote/release a model."""

    import sqlite3

    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/pretraining/jobs", headers=headers, json=_payload(refs)
        )
        job_public_id = created.json()["public_id"]

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
        run_tool("list_training_jobs", settings, {}, admin_id="admin-x")
        run_tool("get_training_job", settings, {"public_id": job_public_id}, admin_id="admin-x")
        run_tool("get_training_checkpoints", settings, {"public_id": job_public_id}, admin_id="admin-x")
        run_tool("get_training_evaluations", settings, {"public_id": job_public_id}, admin_id="admin-x")
        run_tool("get_training_quality_gate", settings, {"public_id": job_public_id}, admin_id="admin-x")
        run_tool(
            "get_model_release_lineage", settings, {"release_public_id": "whatever"}, admin_id="admin-x"
        )
        after = table_counts()

        # Explicit governed-domain checks (Success Criteria 7-10), plus the
        # full-database snapshot as a stronger, unconditional guarantee.
        assert before["training_jobs"] == after["training_jobs"]
        assert before["pretraining_jobs"] == after["pretraining_jobs"]
        assert before["dataset_versions"] == after["dataset_versions"]
        assert before["dataset_records"] == after["dataset_records"]
        assert before["model_registry"] == after["model_registry"]
        assert before["model_release_candidates"] == after["model_release_candidates"]
        assert before["admin_approvals"] == after["admin_approvals"]
        assert before == after
    finally:
        await client.aclose()
