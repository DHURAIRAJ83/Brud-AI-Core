"""Phase 9: Admin Monitoring + Diagnostics -- Admin Assistant integration.

Repository audit (see the Phase 9 final report) found the actual gap
was narrow: `/health`, `/api/admin/system/database`,
`AdminAssistantChatService.llm_status()`, and
`PretrainingReliabilityService.workers()` are all already-built,
authoritative, read-only diagnostic sources -- but NONE were reachable
through Admin Assistant's own tool/chat surface. This phase adds NO new
health-check mechanism, NO anomaly engine, NO background monitoring
worker, and NO polling loop -- only four READ_ONLY tools wrapping
already-existing bounded, deterministic reads verbatim:

- `get_system_health` -- the same `database_is_connected()`/
  `PRAGMA integrity_check`/`migration_status()` primitives the existing
  `/health`/`/api/admin/system/database` routes already use.
- `get_connection_pool_health` -- `ConnectionPool`'s own existing
  thread-safe counters (Phase 7C-27), honestly `unknown` when no pool
  is available in the calling context.
- `get_llm_runtime_health` -- `AdminAssistantChatService.llm_status()`
  verbatim, the same method `/api/admin/assistant/health` already calls.
- `get_worker_health` -- `PretrainingReliabilityService.workers()`
  verbatim, counted by each worker's own real persisted status, never
  an invented rollup.

Every tool follows Step 4's semantics: HEALTHY/DEGRADED/UNAVAILABLE/
UNKNOWN, never a fabricated "healthy" for missing data, and every
recommendation-adjacent status is non-executing -- none of these four
tools can start, stop, or promote anything.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection_pool import ConnectionPool
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.services.admin_assistant_tool_governance import ToolAuthorizationError
from backend.services.admin_assistant_tools import READ_ONLY_TOOLS, ToolCapability, get_tool, run_tool

NONE_ROLE_ADMIN_ID = "d0000000-0000-0000-0000-00000000000d"

NEW_TOOLS = (
    "get_system_health",
    "get_connection_pool_health",
    "get_llm_runtime_health",
    "get_worker_health",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase9.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
        admin_role_overrides=f"{NONE_ROLE_ADMIN_ID}:NONE",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _table_counts(db_path: Path) -> dict[str, int]:
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


# --- 1/2: tool registration / capability classification ---------------------


def test_new_tools_are_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for name in NEW_TOOLS:
        tool = get_tool(name)
        assert tool is not None
        assert tool.capability is ToolCapability.READ_ONLY
        assert tool.needs_admin_id is False
    assert get_tool("get_connection_pool_health").pool_aware is True
    for name in ("get_system_health", "get_llm_runtime_health", "get_worker_health"):
        assert get_tool(name).pool_aware is False


# --- 3/4/5: RBAC enforcement / NONE denial -----------------------------------


@pytest.mark.parametrize("name", NEW_TOOLS)
def test_new_tools_denied_for_none_role(settings: Settings, name: str) -> None:
    with pytest.raises(ToolAuthorizationError):
        run_tool(name, settings, {}, admin_id=NONE_ROLE_ADMIN_ID)


@pytest.mark.parametrize("name", NEW_TOOLS)
def test_new_tools_allowed_for_default_admin_role(settings: Settings, name: str) -> None:
    # Default (unmapped) admin_id resolves to ADMIN, which has tool.read --
    # must not raise.
    result = run_tool(name, settings, {}, admin_id="some-unmapped-admin-id")
    assert result["available"] is True


# --- 6/8/9: health-state correctness, UNKNOWN handling -----------------------


def test_system_health_reports_healthy_for_a_fresh_valid_database(settings: Settings) -> None:
    result = run_tool("get_system_health", settings, {}, admin_id="admin-x")
    assert result["status"] == "healthy"
    assert result["database_connected"] is True
    assert result["database_integrity"] == "ok"
    assert isinstance(result["schema_version"], int)


def test_system_health_unavailable_when_database_unreachable(settings: Settings) -> None:
    # SQLite auto-creates a missing file on connect, so a merely-deleted
    # file is not genuine unavailability -- an unreachable parent
    # directory is: `database_is_connected()` catches the resulting
    # sqlite3.OperationalError and returns False, exactly what a real
    # "database unavailable" condition looks like.
    settings.database_path = Path("/nonexistent-parent-dir-phase9-test/db.sqlite")
    result = run_tool("get_system_health", settings, {}, admin_id="admin-x")
    assert result["status"] == "unavailable"
    assert result["database_connected"] is False


def test_connection_pool_health_is_honestly_unknown_without_a_pool(settings: Settings) -> None:
    result = run_tool("get_connection_pool_health", settings, {}, admin_id="admin-x")
    assert result["status"] == "unknown"
    assert "reason" in result


def test_connection_pool_health_reports_real_counters_with_a_real_pool(settings: Settings) -> None:
    pool = ConnectionPool(settings.resolved_database_path)
    try:
        result = run_tool("get_connection_pool_health", settings, {}, pool=pool, admin_id="admin-x")
        assert result["status"] == "healthy"
        assert result["outstanding"] == 0
        assert isinstance(result["connection_reused_count"], int)
        assert isinstance(result["connection_recreated_count"], int)
        # Never leaks the raw pool object itself.
        assert not any(isinstance(v, ConnectionPool) for v in result.values())
    finally:
        pool.close()


def test_llm_runtime_health_unavailable_with_no_assignment_configured(settings: Settings) -> None:
    result = run_tool("get_llm_runtime_health", settings, {}, admin_id="admin-x")
    assert result["status"] == "unavailable"
    assert result["llm_available"] is False
    assert result["assignment_public_id"] is None


def test_worker_health_is_honestly_unknown_when_no_worker_ever_registered(settings: Settings) -> None:
    result = run_tool("get_worker_health", settings, {}, admin_id="admin-x")
    assert result["status"] == "unknown"
    assert result["worker_count"] == 0
    assert "reason" in result


def test_worker_health_reflects_a_real_registered_worker(settings: Settings) -> None:
    from backend.database.repositories.training_reliability import TrainingReliabilityRepository

    repository = TrainingReliabilityRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        repository.register_worker(connection, "worker-phase9-test")

    result = run_tool("get_worker_health", settings, {}, admin_id="admin-x")
    assert "status" not in result or result.get("status") != "unknown"
    assert result["worker_count"] == 1
    assert sum(result["workers_by_status"].values()) == 1
    assert result["items"][0]["worker_id"] == "worker-phase9-test"


# --- 10: explanation must be grounded, never fabricated ----------------------


def test_no_diagnostic_tool_returns_healthy_for_missing_evidence(settings: Settings) -> None:
    """Cross-cutting: neither the worker nor the LLM tool ever reports
    'healthy' when there is zero underlying evidence -- both use
    'unknown'/'unavailable' explicitly instead."""

    worker = run_tool("get_worker_health", settings, {}, admin_id="admin-x")
    assert worker.get("status", "unknown") != "healthy"
    llm = run_tool("get_llm_runtime_health", settings, {}, admin_id="admin-x")
    assert llm["status"] != "healthy"


# --- 12/13/14/15: no execution, no mutation, governance preserved -----------


def test_new_tools_never_mutate_the_database(settings: Settings) -> None:
    pool = ConnectionPool(settings.resolved_database_path)
    try:
        before = _table_counts(settings.resolved_database_path)
        run_tool("get_system_health", settings, {}, admin_id="admin-x")
        run_tool("get_connection_pool_health", settings, {}, pool=pool, admin_id="admin-x")
        run_tool("get_llm_runtime_health", settings, {}, admin_id="admin-x")
        run_tool("get_worker_health", settings, {}, admin_id="admin-x")
        after = _table_counts(settings.resolved_database_path)
    finally:
        pool.close()

    assert before["training_jobs"] == after["training_jobs"]
    assert before["pretraining_jobs"] == after["pretraining_jobs"]
    assert before["dataset_records"] == after["dataset_records"]
    assert before["model_registry"] == after["model_registry"]
    assert before["admin_approvals"] == after["admin_approvals"]
    assert before == after


def test_new_tools_have_no_write_capability_only_read_only() -> None:
    """OBJECTIVE 5/write-execution boundary: every new tool declares
    ToolCapability.READ_ONLY -- WRITE/PROPOSE/ADMIN_APPROVAL_REQUIRED
    remain unconditionally blocked through run_tool() regardless (Phase
    2/3/4, unmodified), so no new tool could execute a mutation even if
    misconfigured."""

    for name in NEW_TOOLS:
        assert get_tool(name).capability is ToolCapability.READ_ONLY


def test_new_tool_handlers_accept_no_pool_or_connection_except_the_declared_one() -> None:
    import inspect

    from backend.services import admin_assistant_tools as tools_module

    handler_by_tool = {
        "get_system_health": tools_module._tool_get_system_health,
        "get_llm_runtime_health": tools_module._tool_get_llm_runtime_health,
        "get_worker_health": tools_module._tool_get_worker_health,
    }
    for name, handler in handler_by_tool.items():
        sig = inspect.signature(handler)
        for param in sig.parameters.values():
            annotation = str(param.annotation)
            assert "Pool" not in annotation and "sqlite3.Connection" not in annotation
